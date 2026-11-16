"""UnitOfWork (Data/Implementations/unit_of_work.py): session handling, disposal, saving and rolling back staged
changes, and how `_async` repository operations behave inside a unit of work. Runs on SQLite.

The test database starts with the rows described in tests/unit/Data/conftest.py (`bank`); `persisted` reads what
is committed, through a connection of its own. `recording_factory` sessions record the commit / rollback / close /
invalidate calls the unit of work makes.
"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from Data.Implementations.unit_of_work import UnitOfWork
from Data.Interfaces.i_unit_of_work import SaveChangesResult
from Models.Entities import (Account, AccountType, Customer, Role, Staff, Transaction, TransactionMode,
                             TransactionStatus, TransactionType, User)

# SQLAlchemy warnings point at ORM misuse (e.g. an object that will not be saved), so they fail the tests; only
# SQLite's note that it stores DECIMAL as a floating point number is expected.
pytestmark = [pytest.mark.asyncio,
              pytest.mark.filterwarnings("error::sqlalchemy.exc.SAWarning"),
              pytest.mark.filterwarnings("ignore:Dialect sqlite\\+aiosqlite does \\*not\\* support Decimal")]

REPOSITORY_MODELS = [
    ("roles", Role), ("users", User), ("staff", Staff), ("customers", Customer), ("account_types", AccountType),
    ("accounts", Account), ("transaction_types", TransactionType), ("transaction_modes", TransactionMode),
    ("transaction_statuses", TransactionStatus), ("transactions", Transaction),
]

# Every repository operation, called on the `accounts` repository of a unit of work that has ended.
ENDED_UNIT_OF_WORK_OPERATIONS = [
    pytest.param(lambda accounts: accounts.add_single(Account()), id="add_single"),
    pytest.param(lambda accounts: accounts.add_range([Account()]), id="add_range"),
    pytest.param(lambda accounts: accounts.update_single(Account()), id="update_single"),
    pytest.param(lambda accounts: accounts.update_range(Account.Balance > 0, values={"Balance": 0}), id="update_range"),
    pytest.param(lambda accounts: accounts.delete_single(Account()), id="delete_single"),
    pytest.param(lambda accounts: accounts.delete_by_id(uuid.UUID(int=1)), id="delete_by_id"),
    pytest.param(lambda accounts: accounts.delete_range(Account.Balance > 0), id="delete_range"),
    pytest.param(lambda accounts: accounts.save(Account()), id="save"),
    pytest.param(lambda accounts: accounts.get_by_id_async(uuid.UUID(int=1)), id="get_by_id_async"),
    pytest.param(lambda accounts: accounts.get_single_async(Account.Balance > 0), id="get_single_async"),
    pytest.param(lambda accounts: accounts.get_range_async(), id="get_range_async"),
    pytest.param(lambda accounts: accounts.count_async(), id="count_async"),
    pytest.param(lambda accounts: accounts.sum_async(Account.Balance), id="sum_async"),
    pytest.param(lambda accounts: accounts.exists_async(), id="exists_async"),
    pytest.param(lambda accounts: accounts.add_single_async(Account()), id="add_single_async"),
    pytest.param(lambda accounts: accounts.add_range_async([Account()]), id="add_range_async"),
    pytest.param(lambda accounts: accounts.update_single_async(Account()), id="update_single_async"),
    pytest.param(lambda accounts: accounts.update_range_async(Account.Balance > 0, values={"Balance": 0}),
                 id="update_range_async"),
    pytest.param(lambda accounts: accounts.delete_single_async(Account()), id="delete_single_async"),
    pytest.param(lambda accounts: accounts.delete_by_id_async(uuid.UUID(int=1)), id="delete_by_id_async"),
    pytest.param(lambda accounts: accounts.delete_range_async(Account.Balance > 0), id="delete_range_async"),
    pytest.param(lambda accounts: accounts.save_async(Account()), id="save_async"),
]


async def _balance(persisted, bank, number):
    return (await persisted.get(Account, bank.account_id(number))).Balance


# ---------------------------------------------------------------------------
# Lifetime and session handling
# ---------------------------------------------------------------------------

class TestSessionHandling:
    async def test_unit_of_work_is_active_only_inside_its_block(self, session_factory):
        unit_of_work = UnitOfWork(session_factory)
        assert not unit_of_work.is_active

        async with unit_of_work as entered:
            assert entered is unit_of_work
            assert unit_of_work.is_active

        assert not unit_of_work.is_active

    async def test_queries_staged_and_async_operations_share_the_one_session_of_the_block(self, recording_factory,
                                                                                         new_role):
        async with UnitOfWork(recording_factory) as unit_of_work:
            await unit_of_work.accounts.get_range_async()
            unit_of_work.roles.add_single(new_role())
            await unit_of_work.roles.add_single_async(new_role())
            await unit_of_work.accounts.update_range_async(Account.Balance >= 0, values={"Balance": Account.Balance})
            await unit_of_work.save_changes_async()

        assert len(recording_factory.sessions) == 1
        assert recording_factory.sessions[0].calls == ["commit", "commit", "commit", "close"]

    async def test_every_block_gets_a_new_session(self, recording_factory):
        unit_of_work = UnitOfWork(recording_factory)

        for _ in range(2):
            async with unit_of_work:
                await unit_of_work.accounts.count_async()

        assert len(recording_factory.sessions) == 2
        assert recording_factory.sessions[0] is not recording_factory.sessions[1]

    async def test_active_unit_of_work_cannot_be_entered_again(self, unit_of_work):
        with pytest.raises(RuntimeError, match="already active"):
            async with unit_of_work:
                pass

        assert unit_of_work.is_active

    @pytest.mark.parametrize("operation", [
        pytest.param(lambda unit_of_work: unit_of_work.accounts, id="repository-property"),
        pytest.param(lambda unit_of_work: unit_of_work.get_repository(Account), id="get_repository"),
        pytest.param(lambda unit_of_work: unit_of_work.save_changes_async(), id="save_changes_async"),
        pytest.param(lambda unit_of_work: unit_of_work.rollback_async(), id="rollback_async"),
    ])
    async def test_unit_of_work_must_be_active(self, session_factory, operation, result_of):
        with pytest.raises(RuntimeError, match="not active"):
            await result_of(operation(UnitOfWork(session_factory)))

    @pytest.mark.parametrize("name, model", REPOSITORY_MODELS, ids=[name for name, _ in REPOSITORY_MODELS])
    async def test_repository_property_works_on_its_entity(self, unit_of_work, name, model):
        repository = getattr(unit_of_work, name)

        assert repository.model is model
        assert repository is unit_of_work.get_repository(model)

    async def test_one_repository_per_entity_type_in_a_block(self, session_factory):
        unit_of_work = UnitOfWork(session_factory)
        async with unit_of_work:
            first = unit_of_work.accounts
            assert unit_of_work.accounts is first
        async with unit_of_work:
            assert unit_of_work.accounts is not first

    async def test_async_operation_ends_the_transaction_of_the_unit_of_work(self, unit_of_work, engine, new_role):
        await unit_of_work.accounts.count_async()
        assert engine.pool.checkedout() == 1  # the block's transaction holds a connection

        await unit_of_work.roles.add_single_async(new_role())

        assert engine.pool.checkedout() == 0  # committed: connection (and any row locks) released


# ---------------------------------------------------------------------------
# Disposal (end of the block)
# ---------------------------------------------------------------------------

class TestDisposal:
    async def test_session_is_closed_and_its_connection_returned_when_the_block_ends(self, recording_factory, engine):
        async with UnitOfWork(recording_factory) as unit_of_work:
            await unit_of_work.accounts.count_async()
            assert engine.pool.checkedout() == 1

        assert recording_factory.sessions[0].calls == ["close"]
        assert engine.pool.checkedout() == 0

    async def test_leaving_without_saving_discards_the_staged_changes(self, recording_factory, bank, persisted,
                                                                     new_role):
        async with UnitOfWork(recording_factory) as unit_of_work:
            role = unit_of_work.roles.add_single(new_role())
            account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"))
            unit_of_work.accounts.update_single(account, {"Balance": Decimal("1.00")})
            unit_of_work.accounts.delete_by_id(bank.account_id("2600000004"))

        assert recording_factory.sessions[0].calls == ["close"]
        assert await persisted.count(Role, Role.Name == role.Name) == 0
        assert await _balance(persisted, bank, "2600000001") == Decimal("100.00")
        assert await persisted.get(Account, bank.account_id("2600000004")) is not None

    async def test_block_that_raises_is_rolled_back_and_closed_and_the_error_propagates(self, recording_factory,
                                                                                        engine, persisted, new_role):
        with pytest.raises(LookupError, match="stop"):
            async with UnitOfWork(recording_factory) as unit_of_work:
                role = unit_of_work.roles.add_single(new_role())
                await unit_of_work.accounts.count_async()
                raise LookupError("stop")

        assert recording_factory.sessions[0].calls == ["rollback", "close"]
        assert engine.pool.checkedout() == 0
        assert await persisted.count(Role, Role.Name == role.Name) == 0

    async def test_session_that_fails_to_close_is_invalidated(self, closing_fails_factory, engine):
        with pytest.raises(ConnectionError, match="while closing"):
            async with UnitOfWork(closing_fails_factory) as unit_of_work:
                await unit_of_work.accounts.count_async()

        assert closing_fails_factory.sessions[0].calls == ["close", "invalidate"]
        assert engine.pool.checkedout() == 0

    async def test_unit_of_work_is_not_active_after_a_failed_close(self, closing_fails_factory):
        unit_of_work = UnitOfWork(closing_fails_factory)

        with pytest.raises(ConnectionError):
            async with unit_of_work:
                pass

        assert not unit_of_work.is_active

    @pytest.mark.parametrize("operation", ENDED_UNIT_OF_WORK_OPERATIONS)
    async def test_repository_of_an_ended_unit_of_work_stops_working(self, session_factory, operation, result_of):
        async with UnitOfWork(session_factory) as unit_of_work:
            accounts = unit_of_work.accounts

        with pytest.raises(RuntimeError, match="has ended"):
            await result_of(operation(accounts))

    async def test_entities_stay_readable_after_the_block(self, session_factory, bank):
        async with UnitOfWork(session_factory) as unit_of_work:
            account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"), includes=["user"])

        assert inspect(account).detached
        assert (account.Balance, account.user.FirstName) == (Decimal("100.00"), "Ada")

    async def test_entities_keep_their_loaded_values_after_a_block_that_raised(self, session_factory, bank):
        with pytest.raises(LookupError):
            async with UnitOfWork(session_factory) as unit_of_work:
                account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"),
                                                                      includes=["user"])
                unit_of_work.accounts.update_single(account, {"Balance": Decimal("1.00")})
                raise LookupError("stop")

        assert inspect(account).detached
        assert (account.Balance, account.user.FirstName) == (Decimal("100.00"), "Ada")


# ---------------------------------------------------------------------------
# save_changes_async
# ---------------------------------------------------------------------------

class TestSaveChanges:
    async def test_every_staged_change_is_persisted_in_one_commit(self, recording_factory, bank, persisted, new_role):
        async with UnitOfWork(recording_factory) as unit_of_work:
            role = unit_of_work.roles.add_single(new_role())
            account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"))
            unit_of_work.accounts.update_single(account, {"Balance": Decimal("1.00")})
            unit_of_work.accounts.delete_single(
                await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000004")))

            result = await unit_of_work.save_changes_async()

        assert result == SaveChangesResult(added=1, updated=1, deleted=1)
        assert recording_factory.sessions[0].calls == ["commit", "close"]
        assert await persisted.count(Role, Role.Name == role.Name) == 1
        assert await _balance(persisted, bank, "2600000001") == Decimal("1.00")
        assert await persisted.get(Account, bank.account_id("2600000004")) is None

    async def test_nothing_staged_writes_nothing(self, unit_of_work):
        assert await unit_of_work.save_changes_async() == SaveChangesResult()

    async def test_saved_changes_are_not_saved_again(self, unit_of_work, bank, new_role):
        unit_of_work.roles.add_single(new_role())
        account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"))
        unit_of_work.accounts.update_single(account, {"Balance": Decimal("1.00")})
        await unit_of_work.save_changes_async()

        assert await unit_of_work.save_changes_async() == SaveChangesResult()

    async def test_saved_entities_stay_tracked(self, unit_of_work, new_role):
        role = unit_of_work.roles.add_single(new_role())

        await unit_of_work.save_changes_async()

        assert inspect(role).persistent
        assert await unit_of_work.roles.get_by_id_async(role.Id) is role

    @pytest.mark.parametrize("set_first, expected", [(True, "15.00"), (False, "10.00")],
                             ids=["set-then-increment", "increment-then-set"])
    async def test_staged_updates_are_applied_in_call_order(self, unit_of_work, bank, persisted, set_first, expected):
        account_id = bank.account_id("2600000001")
        account = await unit_of_work.accounts.get_by_id_async(account_id)
        steps = [lambda: unit_of_work.accounts.update_single(account, {"Balance": Decimal("10.00")}),
                 lambda: unit_of_work.accounts.update_range(Account.Id == account_id,
                                                            values={"Balance": Account.Balance + 5})]

        for step in (steps if set_first else reversed(steps)):
            step()
        await unit_of_work.save_changes_async()

        assert account.Balance == Decimal(expected)
        assert await _balance(persisted, bank, "2600000001") == Decimal(expected)

    @pytest.mark.parametrize("add_first, expected_count", [(True, 0), (False, 1)],
                             ids=["add-then-delete", "delete-then-add"])
    async def test_staged_adds_and_deletes_are_applied_in_call_order(self, unit_of_work, persisted, add_first,
                                                                     expected_count):
        steps = [lambda: unit_of_work.roles.add_single(Role(Name="Temporary")),
                 lambda: unit_of_work.roles.delete_range(Role.Name == "Temporary")]

        for step in (steps if add_first else reversed(steps)):
            step()
        await unit_of_work.save_changes_async()

        assert await persisted.count(Role, Role.Name == "Temporary") == expected_count

    async def test_result_reports_the_rows_delete_by_id_did_not_find(self, unit_of_work, bank):
        missing_account, missing_type = uuid.UUID(int=7), 999_999
        unit_of_work.accounts.delete_by_id(missing_account)
        unit_of_work.account_types.delete_by_id(missing_type)
        unit_of_work.account_types.delete_by_id(bank.account_type_ids["Retirement"])

        result = await unit_of_work.save_changes_async()

        assert result.deleted == 1
        assert result.not_found == (("Account", missing_account), ("AccountType", missing_type))

    async def test_failed_save_persists_nothing_and_discards_the_staged_changes(self, recording_factory, bank,
                                                                               persisted, new_role):
        async with UnitOfWork(recording_factory) as unit_of_work:
            account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"), includes=["user"])
            unit_of_work.accounts.update_single(account, {"Balance": Decimal("1.00")})
            role = unit_of_work.roles.add_single(new_role())
            unit_of_work.roles.add_single(Role(Name="Customer"))  # the name is taken: the save fails

            with pytest.raises(IntegrityError):
                await unit_of_work.save_changes_async()

            # the entities keep the values they were loaded with, and can still be read
            assert (account.Balance, account.user.FirstName) == (Decimal("100.00"), "Ada")
            assert inspect(role).transient
            # nothing is left staged
            assert await unit_of_work.save_changes_async() == SaveChangesResult()

        assert recording_factory.sessions[0].calls == ["rollback", "commit", "close"]
        assert await _balance(persisted, bank, "2600000001") == Decimal("100.00")
        assert await persisted.count(Role, Role.Name == role.Name) == 0

    async def test_unit_of_work_is_usable_after_a_failed_save(self, unit_of_work, persisted, new_role):
        unit_of_work.roles.add_single(Role(Name="Customer"))
        with pytest.raises(IntegrityError):
            await unit_of_work.save_changes_async()

        role = unit_of_work.roles.add_single(new_role())
        await unit_of_work.save_changes_async()

        assert await persisted.count(Role, Role.Name == role.Name) == 1


# ---------------------------------------------------------------------------
# rollback_async
# ---------------------------------------------------------------------------

class TestRollback:
    async def test_rollback_discards_the_staged_changes_and_entities_keep_their_loaded_values(
            self, unit_of_work, bank, persisted, new_role):
        account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"), includes=["user"])
        unit_of_work.accounts.update_single(account, {"Balance": Decimal("1.00")})
        unit_of_work.roles.add_single(new_role())
        unit_of_work.accounts.delete_by_id(bank.account_id("2600000004"))

        await unit_of_work.rollback_async()

        assert (account.Balance, account.user.FirstName) == (Decimal("100.00"), "Ada")
        assert await unit_of_work.save_changes_async() == SaveChangesResult()
        assert await _balance(persisted, bank, "2600000001") == Decimal("100.00")
        assert await persisted.get(Account, bank.account_id("2600000004")) is not None

    async def test_rollback_ends_the_transaction(self, unit_of_work, engine):
        await unit_of_work.accounts.count_async()
        assert engine.pool.checkedout() == 1

        await unit_of_work.rollback_async()

        assert engine.pool.checkedout() == 0

    async def test_unit_of_work_is_usable_after_a_rollback(self, unit_of_work, persisted, new_role):
        unit_of_work.roles.add_single(new_role())
        await unit_of_work.rollback_async()

        role = unit_of_work.roles.add_single(new_role())
        await unit_of_work.save_changes_async()

        assert await persisted.count(Role) == 3
        assert await persisted.count(Role, Role.Name == role.Name) == 1


# ---------------------------------------------------------------------------
# _async operations inside a unit of work with staged changes
# ---------------------------------------------------------------------------

class TestAsyncOperationsWithStagedChanges:
    async def test_async_operation_commits_only_its_own_data_and_the_staged_changes_stay_staged(
            self, unit_of_work, bank, persisted, new_role):
        account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"))
        unit_of_work.accounts.update_single(account, {"Balance": Decimal("1.00")})
        staged_role = unit_of_work.roles.add_single(new_role())
        unit_of_work.accounts.delete_single(await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000004")))

        persisted_role = await unit_of_work.roles.add_single_async(new_role())

        assert await persisted.count(Role, Role.Name == persisted_role.Name) == 1
        assert await persisted.count(Role, Role.Name == staged_role.Name) == 0
        assert await _balance(persisted, bank, "2600000001") == Decimal("100.00")
        assert await persisted.get(Account, bank.account_id("2600000004")) is not None
        assert account.Balance == Decimal("1.00")  # the staged value is still shown

        assert await unit_of_work.save_changes_async() == SaveChangesResult(added=1, updated=1, deleted=1)
        assert await persisted.count(Role, Role.Name == staged_role.Name) == 1
        assert await _balance(persisted, bank, "2600000001") == Decimal("1.00")
        assert await persisted.get(Account, bank.account_id("2600000004")) is None

    @pytest.mark.parametrize("failing_operation", [
        pytest.param(lambda unit_of_work: unit_of_work.roles.add_single_async(Role(Name="Customer")),
                     id="add_single_async"),
        pytest.param(lambda unit_of_work: unit_of_work.accounts.delete_range_async(Account.Balance >= 100),
                     id="delete_range_async"),  # accounts with transactions: ON DELETE RESTRICT
    ])
    async def test_failed_async_operation_keeps_the_staged_changes(self, unit_of_work, bank, persisted, new_role,
                                                                  failing_operation):
        account = await unit_of_work.accounts.get_by_id_async(bank.account_id("2600000001"), includes=["user"])
        unit_of_work.accounts.update_single(account, {"Balance": Decimal("1.00")})
        staged_role = unit_of_work.roles.add_single(new_role())

        with pytest.raises(IntegrityError):
            await failing_operation(unit_of_work)

        assert (account.Balance, account.user.FirstName) == (Decimal("1.00"), "Ada")
        await unit_of_work.save_changes_async()
        assert await _balance(persisted, bank, "2600000001") == Decimal("1.00")
        assert await persisted.count(Role, Role.Name == staged_role.Name) == 1

    async def test_async_update_of_a_row_with_staged_changes_keeps_them_on_top(self, unit_of_work, bank, persisted):
        account_id = bank.account_id("2600000001")
        account = await unit_of_work.accounts.get_by_id_async(account_id)
        unit_of_work.accounts.update_single(account, {"AccountNumber": "2699999999"})

        await unit_of_work.accounts.update_range_async(Account.Id == account_id,
                                                       values={"Balance": Account.Balance + 5})

        assert (account.Balance, account.AccountNumber) == (Decimal("105.00"), "2699999999")
        stored = await persisted.get(Account, account_id)
        assert (stored.Balance, stored.AccountNumber) == (Decimal("105.00"), "2600000001")

        await unit_of_work.save_changes_async()

        stored = await persisted.get(Account, account_id)
        assert (stored.Balance, stored.AccountNumber) == (Decimal("105.00"), "2699999999")

    async def test_async_update_of_the_tracked_entity_writes_its_staged_changes_too(self, unit_of_work, bank,
                                                                                   persisted):
        account_id = bank.account_id("2600000001")
        account = await unit_of_work.accounts.get_by_id_async(account_id)
        unit_of_work.accounts.update_single(account, {"AccountNumber": "2699999999"})

        await unit_of_work.accounts.update_single_async(account, {"Balance": Decimal("5.00")})

        stored = await persisted.get(Account, account_id)
        assert (stored.Balance, stored.AccountNumber) == (Decimal("5.00"), "2699999999")
        assert await unit_of_work.save_changes_async() == SaveChangesResult()

    async def test_async_delete_of_a_row_with_staged_changes_drops_them(self, unit_of_work, bank, persisted):
        account_id = bank.account_id("2600000004")
        account = await unit_of_work.accounts.get_by_id_async(account_id)
        unit_of_work.accounts.update_single(account, {"Balance": Decimal("1.00")})

        assert await unit_of_work.accounts.delete_by_id_async(account_id) is True

        assert await unit_of_work.save_changes_async() == SaveChangesResult()
        assert await persisted.get(Account, account_id) is None

    async def test_queries_after_an_async_operation_see_the_latest_committed_data(self, unit_of_work, bank,
                                                                                 session_factory):
        assert await unit_of_work.accounts.count_async() == 5
        async with session_factory() as other_session:  # another connection commits a change meanwhile
            await other_session.delete(await other_session.get(Account, bank.account_id("2600000004")))
            await other_session.commit()

        await unit_of_work.roles.add_single_async(Role(Name="Auditor"))

        assert await unit_of_work.accounts.count_async() == 4
