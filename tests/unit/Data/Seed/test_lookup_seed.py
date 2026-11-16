"""Data/Seed/lookup_seed.py: the lookup rows the services refer to through AppConstants.

An empty database (schema only) stands for a first run; the `bank` test database (tests/unit/Data/conftest.py)
stands for a database that is already in use and misses two rows (the Withdrawal type and the Failed status).
"""
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock

from Data.Implementations.unit_of_work import UnitOfWork
from Data.Seed import lookup_seed
from Data.Seed.lookup_seed import (LOOKUP_SEEDS, LookupSeedError, is_database_seeded_async,
                                   missing_lookup_rows_async, seed_lookups_async, seed_lookups_on_first_run_async)
from Models.Constants.AppConstants import AppConstants
from Models.Entities import AccountType, Base, Role, TransactionMode, TransactionStatus, TransactionType

pytestmark = [pytest.mark.filterwarnings("error::sqlalchemy.exc.SAWarning")]

EXPECTED_ROWS = {
    Role: {AppConstants.CustomerRoleId: "Customer", AppConstants.StaffRoleId: "Staff"},
    AccountType: {AppConstants.SavingsAccountTypeId: "Savings", AppConstants.CurrentAccountTypeId: "Current"},
    TransactionType: {AppConstants.DepositTransactionTypeId: "Deposit",
                      AppConstants.TransferTransactionTypeId: "Transfer",
                      AppConstants.WithdrawalTransactionTypeId: "Withdrawal"},
    TransactionMode: {AppConstants.CreditTransactionModeId: "Credit", AppConstants.DebitTransactionModeId: "Debit"},
    TransactionStatus: {AppConstants.PendingTransactionStatusId: "Pending",
                        AppConstants.CompletedTransactionStatusId: "Completed",
                        AppConstants.FailedTransactionStatusId: "Failed"},
}
ROW_COUNT = sum(len(rows) for rows in EXPECTED_ROWS.values())

# The rows the `bank` test database does not have.
BANK_MISSING_ROWS = {TransactionType: {AppConstants.WithdrawalTransactionTypeId: "Withdrawal"},
                     TransactionStatus: {AppConstants.FailedTransactionStatusId: "Failed"}}

# Which lookup table each AppConstants identifier belongs to (by the end of the constant's name).
CONSTANT_SUFFIXES = {"RoleId": Role, "AccountTypeId": AccountType, "TransactionTypeId": TransactionType,
                     "TransactionModeId": TransactionMode, "TransactionStatusId": TransactionStatus}


@pytest_asyncio.fixture
async def empty_session_factory():
    """A new database with the schema and no rows: the application runs for the first time."""
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


async def _rows(session_factory):
    async with session_factory() as session:
        rows = {}
        for seed in LOOKUP_SEEDS:
            entities = (await session.scalars(select(seed.model))).all()
            rows[seed.model] = {entity.Id: getattr(entity, seed.name_attribute) for entity in entities}
        return rows


# ---------------------------------------------------------------------------
# The seed data
# ---------------------------------------------------------------------------

def test_seed_rows_use_the_identifiers_of_app_constants():
    assert {seed.model: seed.rows for seed in LOOKUP_SEEDS} == EXPECTED_ROWS


@pytest.mark.parametrize("seed", LOOKUP_SEEDS, ids=lambda seed: seed.model.__name__)
def test_identifiers_and_names_are_unique_per_table(seed):
    assert len(set(seed.rows.values())) == len(seed.rows)


@pytest.mark.parametrize("constant", [name for name in vars(AppConstants) if name.endswith("Id")])
def test_every_lookup_identifier_constant_is_seeded(constant):
    model = next(model for suffix, model in CONSTANT_SUFFIXES.items() if constant.endswith(suffix))
    seeded = next(seed for seed in LOOKUP_SEEDS if seed.model is model)

    assert getattr(AppConstants, constant) in seeded.rows


def test_no_two_constants_of_a_table_share_an_identifier():
    for suffix in CONSTANT_SUFFIXES:
        values = [value for name, value in vars(AppConstants).items() if name.endswith(suffix)]
        assert len(values) == len(set(values)), suffix


# ---------------------------------------------------------------------------
# First run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestFirstRun:
    async def test_new_database_is_not_seeded(self, empty_session_factory):
        async with UnitOfWork(empty_session_factory) as unit_of_work:
            assert await is_database_seeded_async(unit_of_work) is False
            assert await missing_lookup_rows_async(unit_of_work) == EXPECTED_ROWS

    async def test_missing_rows_of_a_database_in_use(self, session_factory, bank):
        async with UnitOfWork(session_factory) as unit_of_work:
            assert await missing_lookup_rows_async(unit_of_work) == BANK_MISSING_ROWS

    async def test_first_run_seeds_every_lookup_row(self, empty_session_factory):
        async with UnitOfWork(empty_session_factory) as unit_of_work:
            added = await seed_lookups_on_first_run_async(unit_of_work)

        assert added == ROW_COUNT
        assert await _rows(empty_session_factory) == EXPECTED_ROWS

    async def test_later_runs_only_check_and_never_write(self, empty_session_factory, monkeypatch):
        async with UnitOfWork(empty_session_factory) as unit_of_work:
            await seed_lookups_on_first_run_async(unit_of_work)

        async with UnitOfWork(empty_session_factory) as unit_of_work:
            save = AsyncMock(wraps=unit_of_work.save_changes_async)
            monkeypatch.setattr(unit_of_work, "save_changes_async", save)
            assert await is_database_seeded_async(unit_of_work) is True
            assert await seed_lookups_on_first_run_async(unit_of_work) == 0

        save.assert_not_awaited()
        assert await _rows(empty_session_factory) == EXPECTED_ROWS

    async def test_partly_seeded_database_is_completed_at_start_up(self, session_factory, bank):
        before = await _rows(session_factory)

        async with UnitOfWork(session_factory) as unit_of_work:
            assert await is_database_seeded_async(unit_of_work) is False
            assert await seed_lookups_on_first_run_async(unit_of_work) == 2

        after = await _rows(session_factory)
        assert {model: {row_id: after[model][row_id] for row_id in rows}
                for model, rows in BANK_MISSING_ROWS.items()} == BANK_MISSING_ROWS
        for model, rows in before.items():  # existing rows (e.g. the Retirement account type) are kept
            assert rows.items() <= after[model].items()

    async def test_completed_database_is_not_written_again(self, session_factory, bank, monkeypatch):
        async with UnitOfWork(session_factory) as unit_of_work:
            await seed_lookups_on_first_run_async(unit_of_work)
        before = await _rows(session_factory)

        async with UnitOfWork(session_factory) as unit_of_work:
            save = AsyncMock(wraps=unit_of_work.save_changes_async)
            monkeypatch.setattr(unit_of_work, "save_changes_async", save)
            assert await seed_lookups_on_first_run_async(unit_of_work) == 0

        save.assert_not_awaited()
        assert await _rows(session_factory) == before

    async def test_rows_seeded_by_another_instance_meanwhile_are_accepted(self, empty_session_factory, monkeypatch):
        # Both instances found rows missing; the other one saved first, so this save hits the unique keys.
        async def other_instance_seeds_first(unit_of_work):
            async with UnitOfWork(empty_session_factory) as other:
                await seed_lookups_async(other)
            raise IntegrityError("INSERT ...", {}, Exception("UNIQUE constraint failed: Roles.Name"))

        monkeypatch.setattr(lookup_seed, "seed_lookups_async", other_instance_seeds_first)

        async with UnitOfWork(empty_session_factory) as unit_of_work:
            assert await seed_lookups_on_first_run_async(unit_of_work) == 0

        assert await _rows(empty_session_factory) == EXPECTED_ROWS

    async def test_failed_save_with_rows_still_missing_is_an_error(self, empty_session_factory, monkeypatch):
        monkeypatch.setattr(lookup_seed, "seed_lookups_async",
                            AsyncMock(side_effect=IntegrityError("INSERT ...", {}, Exception("refused"))))

        async with UnitOfWork(empty_session_factory) as unit_of_work:
            with pytest.raises(LookupSeedError, match="still missing: Roles 1 'Customer'") as exc_info:
                await seed_lookups_on_first_run_async(unit_of_work)

        assert isinstance(exc_info.value.__cause__, IntegrityError)

    async def test_contradicting_lookup_data_stops_the_start_up(self, empty_session_factory):
        # "Customer" exists with another identifier: the rows of AppConstants cannot be added.
        async with empty_session_factory() as session:
            session.add(Role(Id=5, Name="Customer"))
            await session.commit()

        async with UnitOfWork(empty_session_factory) as unit_of_work:
            with pytest.raises(LookupSeedError, match="Roles 'Customer' has Id 5, AppConstants expects Id 1"):
                await seed_lookups_on_first_run_async(unit_of_work)

        assert await _rows(empty_session_factory) == {**{model: {} for model in EXPECTED_ROWS}, Role: {5: "Customer"}}


# ---------------------------------------------------------------------------
# Explicit seeding (python -m Data.Seed.lookup_seed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestExplicitSeeding:
    async def test_adds_only_the_missing_rows(self, session_factory, bank):
        # The bank database has no Withdrawal type and no Failed status.
        before = await _rows(session_factory)

        async with UnitOfWork(session_factory) as unit_of_work:
            added = await seed_lookups_async(unit_of_work)

        after = await _rows(session_factory)
        assert added == 2
        assert after[TransactionType] == {**before[TransactionType], AppConstants.WithdrawalTransactionTypeId:
                                          "Withdrawal"}
        assert after[TransactionStatus] == {**before[TransactionStatus], AppConstants.FailedTransactionStatusId:
                                            "Failed"}
        assert {model: rows for model, rows in after.items() if model not in (TransactionType, TransactionStatus)} == \
            {model: rows for model, rows in before.items() if model not in (TransactionType, TransactionStatus)}

    async def test_nothing_missing_means_nothing_saved(self, empty_session_factory, monkeypatch):
        async with UnitOfWork(empty_session_factory) as unit_of_work:
            await seed_lookups_async(unit_of_work)

        async with UnitOfWork(empty_session_factory) as unit_of_work:
            save = AsyncMock(wraps=unit_of_work.save_changes_async)
            monkeypatch.setattr(unit_of_work, "save_changes_async", save)
            assert await seed_lookups_async(unit_of_work) == 0

        save.assert_not_awaited()

    async def test_existing_rows_are_never_changed(self, empty_session_factory, caplog):
        async with empty_session_factory() as session:
            session.add(Role(Id=AppConstants.CustomerRoleId, Name="Client"))
            await session.commit()

        async with UnitOfWork(empty_session_factory) as unit_of_work:
            await seed_lookups_async(unit_of_work)

        assert (await _rows(empty_session_factory))[Role] == {AppConstants.CustomerRoleId: "Client",
                                                              AppConstants.StaffRoleId: "Staff"}
        assert "Roles Id 1 is named 'Client', AppConstants expects 'Customer'" in caplog.text

    async def test_contradicting_lookup_data_is_reported_before_writing(self, empty_session_factory):
        async with empty_session_factory() as session:
            session.add_all([Role(Id=7, Name="Staff"), TransactionMode(Id=9, Name="Credit")])
            await session.commit()

        async with UnitOfWork(empty_session_factory) as unit_of_work:
            with pytest.raises(LookupSeedError) as exc_info:
                await seed_lookups_async(unit_of_work)

        assert "Roles 'Staff' has Id 7, AppConstants expects Id 2" in str(exc_info.value)
        assert "TransactionModes 'Credit' has Id 9, AppConstants expects Id 1" in str(exc_info.value)
        rows = await _rows(empty_session_factory)
        assert (rows[Role], rows[TransactionMode], rows[AccountType]) == ({7: "Staff"}, {9: "Credit"}, {})
