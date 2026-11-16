"""Services/Extensions/exception_handler.py: database and validation errors translated into domain errors.

Database errors are given as each database reports them: MySQL / MariaDB error numbers and messages, PostgreSQL
SQLSTATE codes, SQLite messages - the latter also raised for real by the SQLite test database.
"""
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

from Data.Interfaces.i_unit_of_work import IUnitOfWork, SaveChangesResult
from Models.Dtos.Request.base_request import AccountNumber, Amount, Description
from Models.Entities import Account, AccountType, Role
from Services.Exceptions.domain_exceptions import (BusinessRuleError, ConflictError, DeleteRestrictedError,
                                                   InvalidInputError, NotFoundError, PersistenceError)
from Services.Extensions.exception_handler import (CHECK_MESSAGES, DEFAULT_CONFLICT_MESSAGE, DEFAULT_FAILED_MESSAGE,
                                                   DEFAULT_MISSING_MESSAGE, DEFAULT_RULE_MESSAGE,
                                                   OUT_OF_RANGE_MESSAGE, IntegrityViolation, ViolationKind, _adapter,
                                                   integrity_constraint_name, integrity_violation, save_changes_async,
                                                   service_error_for, validated)
from tests.unit.Services.conftest import SERVICE_TEST_MARKS

pytestmark = SERVICE_TEST_MARKS


class _DriverError(Exception):
    """Stands in for a database driver's exception (the `orig` of SQLAlchemy's IntegrityError)."""


def _integrity_error(*driver_args, **attributes):
    original = _DriverError(*driver_args)
    for name, value in attributes.items():
        setattr(original, name, value)
    return IntegrityError("INSERT ...", {}, original)


# ---------------------------------------------------------------------------
# Classification: the kind of violation and the constraint
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("error, expected", [
    # MySQL / MariaDB: (error number, message)
    pytest.param(_integrity_error(1062, "Duplicate entry '2600000001' for key 'Accounts.uq_Accounts_AccountNumber'"),
                 IntegrityViolation(ViolationKind.UNIQUE, "uq_Accounts_AccountNumber"), id="mysql-8-duplicate"),
    pytest.param(_integrity_error(1062, "Duplicate entry 'example1@example.com' for key 'uq_Users_Email'"),
                 IntegrityViolation(ViolationKind.UNIQUE, "uq_Users_Email"), id="mysql-duplicate"),
    pytest.param(_integrity_error(1062, "Duplicate entry 'a.b-1' for key 'Accounts.uq_Accounts_UserId_AccountTypeId'"),
                 IntegrityViolation(ViolationKind.UNIQUE, "uq_Accounts_UserId_AccountTypeId"),
                 id="mysql-duplicate-value-with-dots"),
    pytest.param(_integrity_error(1451, "Cannot delete or update a parent row: a foreign key constraint fails (`bank`."
                                        "`Accounts`, CONSTRAINT `fk_Accounts_UserId_Users` FOREIGN KEY (`UserId`) "
                                        "REFERENCES `Users` (`Id`))"),
                 IntegrityViolation(ViolationKind.FOREIGN_KEY, "fk_Accounts_UserId_Users"), id="mysql-parent-in-use"),
    pytest.param(_integrity_error(1452, "Cannot add or update a child row: a foreign key constraint fails (`bank`."
                                        "`Accounts`, CONSTRAINT `fk_Accounts_AccountTypeId_AccountTypes` FOREIGN KEY "
                                        "(`AccountTypeId`) REFERENCES `AccountTypes` (`Id`))"),
                 IntegrityViolation(ViolationKind.FOREIGN_KEY, "fk_Accounts_AccountTypeId_AccountTypes"),
                 id="mysql-missing-parent"),
    pytest.param(_integrity_error(3819, "Check constraint 'ck_Accounts_balance_non_negative' is violated."),
                 IntegrityViolation(ViolationKind.CHECK, "ck_Accounts_balance_non_negative"), id="mysql-check"),
    pytest.param(_integrity_error(4025, "CONSTRAINT `ck_Transactions_amount_positive` failed for `bank`."
                                        "`Transactions`"),
                 IntegrityViolation(ViolationKind.CHECK, "ck_Transactions_amount_positive"), id="mariadb-check"),
    pytest.param(_integrity_error(1048, "Column 'Name' cannot be null"),
                 IntegrityViolation(ViolationKind.NOT_NULL, None), id="mysql-not-null"),
    # PostgreSQL: SQLSTATE and the constraint name in structured fields
    pytest.param(_integrity_error("duplicate key value", sqlstate="23505",
                                  diag=SimpleNamespace(constraint_name="uq_Users_Email")),
                 IntegrityViolation(ViolationKind.UNIQUE, "uq_Users_Email"), id="postgresql-unique"),
    pytest.param(_integrity_error("violates foreign key constraint", pgcode="23503",
                                  diag=SimpleNamespace(constraint_name="fk_Staff_UserId_Users")),
                 IntegrityViolation(ViolationKind.FOREIGN_KEY, "fk_Staff_UserId_Users"), id="postgresql-foreign-key"),
    pytest.param(_integrity_error("violates check constraint", sqlstate="23514",
                                  diag=SimpleNamespace(constraint_name="ck_Accounts_balance_non_negative")),
                 IntegrityViolation(ViolationKind.CHECK, "ck_Accounts_balance_non_negative"), id="postgresql-check"),
    pytest.param(_integrity_error("null value in column", sqlstate="23502", diag=SimpleNamespace(constraint_name=None)),
                 IntegrityViolation(ViolationKind.NOT_NULL, None), id="postgresql-not-null"),
    # SQLite: the message
    pytest.param(_integrity_error("UNIQUE constraint failed: Accounts.AccountNumber"),
                 IntegrityViolation(ViolationKind.UNIQUE, "uq_Accounts_AccountNumber"), id="sqlite-unique"),
    pytest.param(_integrity_error("UNIQUE constraint failed: Accounts.UserId, Accounts.AccountTypeId"),
                 IntegrityViolation(ViolationKind.UNIQUE, "uq_Accounts_UserId_AccountTypeId"),
                 id="sqlite-composite-unique"),
    pytest.param(_integrity_error("FOREIGN KEY constraint failed"),
                 IntegrityViolation(ViolationKind.FOREIGN_KEY, None), id="sqlite-foreign-key"),
    pytest.param(_integrity_error("CHECK constraint failed: ck_Accounts_balance_non_negative"),
                 IntegrityViolation(ViolationKind.CHECK, "ck_Accounts_balance_non_negative"), id="sqlite-check"),
    pytest.param(_integrity_error("NOT NULL constraint failed: Roles.Name"),
                 IntegrityViolation(ViolationKind.NOT_NULL, None), id="sqlite-not-null"),
    # Anything else
    pytest.param(_integrity_error("refused by a trigger"), IntegrityViolation(ViolationKind.OTHER, None), id="other"),
])
def test_violation_is_classified(error, expected):
    assert integrity_violation(error) == expected
    assert integrity_constraint_name(error) == expected.constraint_name


@pytest.mark.asyncio
class TestRealDatabaseViolations:
    """The same classification for errors raised by the SQLite test database."""

    async def _violation(self, unit_of_work, stage):
        stage(unit_of_work)
        with pytest.raises(IntegrityError) as exc_info:
            await unit_of_work.save_changes_async()
        return integrity_violation(exc_info.value)

    async def test_unique(self, unit_of_work):
        violation = await self._violation(unit_of_work,
                                          lambda work: work.account_types.add_single(AccountType(Type="Savings")))

        assert violation == IntegrityViolation(ViolationKind.UNIQUE, "uq_AccountTypes_Type")

    async def test_foreign_key_of_a_new_row(self, unit_of_work):
        violation = await self._violation(unit_of_work, lambda work: work.accounts.add_single(
            Account(UserId=uuid.UUID(int=404), AccountTypeId=1, AccountNumber="2690000001")))

        assert violation.kind is ViolationKind.FOREIGN_KEY

    async def test_foreign_key_of_a_deleted_row(self, unit_of_work):
        violation = await self._violation(unit_of_work, lambda work: work.roles.delete_by_id(1))

        assert violation.kind is ViolationKind.FOREIGN_KEY

    async def test_check(self, unit_of_work, bank):
        violation = await self._violation(unit_of_work, lambda work: work.accounts.add_single(
            Account(UserId=bank.user_ids["Cy"], AccountTypeId=bank.account_type_ids["Current"],
                    AccountNumber="2690000001", Balance=Decimal("-1.00"))))

        assert violation == IntegrityViolation(ViolationKind.CHECK, "ck_Accounts_balance_non_negative")

    async def test_not_null(self, unit_of_work):
        violation = await self._violation(unit_of_work, lambda work: work.roles.add_single(Role(Name=None)))

        assert violation.kind is ViolationKind.NOT_NULL


# ---------------------------------------------------------------------------
# service_error_for: the domain error of each kind
# ---------------------------------------------------------------------------

UNIQUE = _integrity_error("UNIQUE constraint failed: Users.Email")
FOREIGN_KEY = _integrity_error("FOREIGN KEY constraint failed")
BALANCE_CHECK = _integrity_error("CHECK constraint failed: ck_Accounts_balance_non_negative")
UNKNOWN_CHECK = _integrity_error("CHECK constraint failed: ck_Other_rule")
NOT_NULL = _integrity_error("NOT NULL constraint failed: Roles.Name")
OTHER = _integrity_error("refused by a trigger")


@pytest.mark.parametrize("error, arguments, expected_type, expected_message", [
    pytest.param(UNIQUE, {}, ConflictError, DEFAULT_CONFLICT_MESSAGE, id="unique"),
    pytest.param(UNIQUE, {"conflict": "Taken."}, ConflictError, "Taken.", id="unique-message"),
    pytest.param(UNIQUE, {"conflict": "Taken.", "conflicts": {"uq_Users_Email": "Email taken."}}, ConflictError,
                 "Email taken.", id="unique-message-of-the-constraint"),
    pytest.param(UNIQUE, {"conflicts": {"uq_Accounts_AccountNumber": "Number taken."}}, ConflictError,
                 DEFAULT_CONFLICT_MESSAGE, id="unique-other-constraint"),
    pytest.param(FOREIGN_KEY, {"restricted": "In use."}, DeleteRestrictedError, "In use.", id="foreign-key-delete"),
    pytest.param(FOREIGN_KEY, {}, NotFoundError, DEFAULT_MISSING_MESSAGE, id="foreign-key-missing-row"),
    pytest.param(FOREIGN_KEY, {"missing": "Gone."}, NotFoundError, "Gone.", id="foreign-key-missing-row-message"),
    pytest.param(BALANCE_CHECK, {}, BusinessRuleError, CHECK_MESSAGES["ck_Accounts_balance_non_negative"],
                 id="known-check"),
    pytest.param(UNKNOWN_CHECK, {}, BusinessRuleError, DEFAULT_RULE_MESSAGE, id="other-check"),
    pytest.param(NOT_NULL, {}, PersistenceError, DEFAULT_FAILED_MESSAGE, id="not-null"),
    pytest.param(OTHER, {}, PersistenceError, DEFAULT_FAILED_MESSAGE, id="other"),
    pytest.param(OTHER, {"failed": "Not saved.", "conflict": "Taken."}, PersistenceError, "Not saved.",
                 id="other-message"),
])
def test_violation_becomes_the_matching_domain_error(error, arguments, expected_type, expected_message):
    domain_error = service_error_for(error, **arguments)

    assert type(domain_error) is expected_type
    assert domain_error.message == expected_message


@pytest.mark.parametrize("error", [FOREIGN_KEY, BALANCE_CHECK, NOT_NULL, OTHER], ids=["foreign-key", "check",
                                                                                       "not-null", "other"])
def test_only_unique_violations_are_conflicts(error):
    # (A foreign key violation of a delete is a DeleteRestrictedError, which the caller asks for with `restricted`.)
    assert not isinstance(service_error_for(error, conflict="Taken."), ConflictError)


def test_every_check_constraint_of_the_entities_has_a_message():
    from Models.Entities import Base

    names = {constraint.name for table in Base.metadata.tables.values() for constraint in table.constraints
             if constraint.__class__.__name__ == "CheckConstraint"}

    assert names == set(CHECK_MESSAGES)


# ---------------------------------------------------------------------------
# save_changes_async
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_unit_of_work():
    unit_of_work = MagicMock(spec=IUnitOfWork)
    unit_of_work.save_changes_async = AsyncMock(return_value=SaveChangesResult(added=1))
    return unit_of_work


@pytest.mark.asyncio
class TestSaveChanges:
    async def test_successful_save_returns_what_was_written(self, mock_unit_of_work):
        assert await save_changes_async(mock_unit_of_work) == SaveChangesResult(added=1)
        mock_unit_of_work.save_changes_async.assert_awaited_once_with()

    @pytest.mark.parametrize("error, arguments, expected_type", [
        pytest.param(UNIQUE, {"conflict": "Taken."}, ConflictError, id="unique"),
        pytest.param(FOREIGN_KEY, {"restricted": "In use."}, DeleteRestrictedError, id="delete-restricted"),
        pytest.param(FOREIGN_KEY, {}, NotFoundError, id="missing-row"),
        pytest.param(BALANCE_CHECK, {}, BusinessRuleError, id="check"),
        pytest.param(OTHER, {"failed": "Not saved."}, PersistenceError, id="other"),
    ])
    async def test_violation_is_raised_as_its_domain_error(self, mock_unit_of_work, error, arguments, expected_type):
        mock_unit_of_work.save_changes_async.side_effect = error

        with pytest.raises(expected_type) as exc_info:
            await save_changes_async(mock_unit_of_work, **arguments)

        assert exc_info.value.__cause__ is error

    async def test_value_the_database_cannot_store_is_invalid_input(self, mock_unit_of_work):
        out_of_range = DataError("UPDATE ...", {}, _DriverError(1264, "Out of range value for column 'Balance'"))
        mock_unit_of_work.save_changes_async.side_effect = out_of_range

        with pytest.raises(InvalidInputError) as exc_info:
            await save_changes_async(mock_unit_of_work)

        assert exc_info.value.message == OUT_OF_RANGE_MESSAGE
        assert exc_info.value.__cause__ is out_of_range

    async def test_other_database_errors_are_not_hidden(self, mock_unit_of_work):
        failure = OperationalError("UPDATE ...", {}, _DriverError("connection lost"))
        mock_unit_of_work.save_changes_async.side_effect = failure

        with pytest.raises(OperationalError) as exc_info:
            await save_changes_async(mock_unit_of_work)

        assert exc_info.value is failure

    async def test_refused_save_against_the_database_writes_nothing(self, unit_of_work, persisted, bank):
        # A balance below zero (ck_Accounts_balance_non_negative): a business rule, not a conflict.
        unit_of_work.accounts.add_single(Account(UserId=bank.user_ids["Cy"],
                                                 AccountTypeId=bank.account_type_ids["Current"],
                                                 AccountNumber="2690000001", Balance=Decimal("-1.00")))

        with pytest.raises(BusinessRuleError, match="cannot become negative"):
            await save_changes_async(unit_of_work, conflict="Taken.")

        assert await persisted.count(Account) == 5


# ---------------------------------------------------------------------------
# validated
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field_type, value, expected", [
    pytest.param(Amount, "25.5", Decimal("25.50"), id="amount-text"),
    pytest.param(Amount, 3500, Decimal("3500.00"), id="amount-integer"),
    pytest.param(AccountNumber, " 2600000001 ", "2600000001", id="account-number-trimmed"),
    pytest.param(Description, "   ", None, id="blank-description"),
])
def test_valid_value_is_returned_normalised(field_type, value, expected):
    result = validated(field_type, value, "value")

    assert result == expected
    assert type(result) is type(expected)


@pytest.mark.parametrize("field_type, value, field_name", [
    pytest.param(Amount, 25.5, "amount", id="float-amount"),
    pytest.param(Amount, "0.00", "amount", id="zero-amount"),
    pytest.param(Amount, "1.234", "amount", id="three-places"),
    pytest.param(AccountNumber, "12345", "account number", id="short-account-number"),
    pytest.param(AccountNumber, 2600000001, "account number", id="account-number-as-integer"),
])
def test_invalid_value_is_an_invalid_input_error(field_type, value, field_name):
    with pytest.raises(InvalidInputError) as exc_info:
        validated(field_type, value, field_name)

    assert exc_info.value.message.startswith(f"Invalid {field_name}: ")
    assert str(value) not in exc_info.value.message  # the submitted value is not echoed
    assert exc_info.value.__cause__ is None


def test_validators_are_built_once_per_field_type():
    assert _adapter(Amount) is _adapter(Amount)
    assert _adapter(Amount) is not _adapter(AccountNumber)
