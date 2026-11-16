"""Translation of data access and validation errors into the services' domain errors.

When the database refuses to save (an IntegrityError), the kind of rule it enforced decides the domain error:

=============  ===========================================================  ===========================
Violation      Meaning                                                      Domain error
=============  ===========================================================  ===========================
unique         the value is taken by another row                            ConflictError
foreign key    a delete: other rows still refer to the row                  DeleteRestrictedError
               an insert / update: the row referred to no longer exists     NotFoundError
check          a rule on the stored values (e.g. a balance below zero)      BusinessRuleError
not null       a required value is missing                                  PersistenceError
other          anything else the database refused                           PersistenceError
=============  ===========================================================  ===========================

A value the database cannot store (a DataError, e.g. a number out of range) is an InvalidInputError.
"""
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, TypeVar

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.exc import DataError, IntegrityError

from Data.Interfaces.i_unit_of_work import IUnitOfWork, SaveChangesResult
from Models.Entities.base_entity import NAMING_CONVENTION
from Services.Exceptions.domain_exceptions import (BusinessRuleError, ConflictError, DeleteRestrictedError,
                                                   InvalidInputError, NotFoundError, PersistenceError, ServiceError)

T = TypeVar("T")

DEFAULT_CONFLICT_MESSAGE = "The data conflicts with existing data."
DEFAULT_MISSING_MESSAGE = "A record the operation refers to no longer exists."
DEFAULT_FAILED_MESSAGE = "The changes could not be saved."
DEFAULT_RULE_MESSAGE = "The change breaks a rule of the stored data."
OUT_OF_RANGE_MESSAGE = "A value is outside the range the database can store."
# Messages never repeat an email address or an account number: they are personal data.
EMAIL_IN_USE_MESSAGE = "The email address is already in use."

# The check constraints of the entities (names from NAMING_CONVENTION) and what they mean.
CHECK_MESSAGES = {
    "ck_Accounts_balance_non_negative": "The balance of an account cannot become negative.",
    "ck_Transactions_amount_positive": "A transaction amount must be greater than zero.",
}


class ViolationKind(Enum):
    UNIQUE = "unique"
    FOREIGN_KEY = "foreign key"
    CHECK = "check"
    NOT_NULL = "not null"
    OTHER = "other"


@dataclass(frozen=True)
class IntegrityViolation:
    """What an IntegrityError says: the kind of rule the database enforced and, when it said so, the constraint."""

    kind: ViolationKind
    constraint_name: Optional[str] = None


# PostgreSQL SQLSTATE codes and MySQL / MariaDB error numbers of each kind of violation.
_SQLSTATE_KINDS = {"23505": ViolationKind.UNIQUE, "23503": ViolationKind.FOREIGN_KEY, "23514": ViolationKind.CHECK,
                   "23502": ViolationKind.NOT_NULL}
_MYSQL_ERROR_KINDS = {1062: ViolationKind.UNIQUE, 1169: ViolationKind.UNIQUE, 1586: ViolationKind.UNIQUE,
                      1216: ViolationKind.FOREIGN_KEY, 1217: ViolationKind.FOREIGN_KEY,
                      1451: ViolationKind.FOREIGN_KEY, 1452: ViolationKind.FOREIGN_KEY,
                      3819: ViolationKind.CHECK, 4025: ViolationKind.CHECK,
                      1048: ViolationKind.NOT_NULL, 1364: ViolationKind.NOT_NULL}
# SQLite says it in the message.
_SQLITE_MESSAGE_KINDS = {"UNIQUE constraint failed": ViolationKind.UNIQUE,
                         "FOREIGN KEY constraint failed": ViolationKind.FOREIGN_KEY,
                         "CHECK constraint failed": ViolationKind.CHECK,
                         "NOT NULL constraint failed": ViolationKind.NOT_NULL}

# MySQL / MariaDB: "Duplicate entry '...' for key 'Accounts.uq_Accounts_AccountNumber'" (MySQL 8.0.19+ prefixes the
# table name), "... a foreign key constraint fails (..., CONSTRAINT `fk_...` FOREIGN KEY ...)",
# "Check constraint 'ck_...' is violated." (MySQL) and "CONSTRAINT `ck_...` failed for ..." (MariaDB).
_MYSQL_DUPLICATE_KEY = re.compile(r"for key '(?:[^'.]+\.)?([^'.]+)'")
_MYSQL_CONSTRAINT = re.compile(r"CONSTRAINT `([^`]+)`")
_MYSQL_CHECK = re.compile(r"Check constraint '([^']+)' is violated")
# SQLite names the columns of a unique constraint, not the constraint: "UNIQUE constraint failed: Accounts.UserId,
# Accounts.AccountTypeId"; a check constraint by its name: "CHECK constraint failed: ck_Accounts_balance_non_negative".
_SQLITE_UNIQUE = re.compile(r"UNIQUE constraint failed: ([\w.]+(?:, [\w.]+)*)")
_SQLITE_CHECK = re.compile(r"CHECK constraint failed: (\w+)")


def integrity_violation(error: IntegrityError) -> IntegrityViolation:
    """The kind of rule an IntegrityError reports and the constraint it names (see the module documentation)."""
    return IntegrityViolation(_violation_kind(error.orig), integrity_constraint_name(error))


def integrity_constraint_name(error: IntegrityError) -> Optional[str]:
    """The name of the constraint a violation reported by the database refers to, e.g. "uq_Accounts_AccountNumber";
    None when the database did not say.

    Constraint names follow NAMING_CONVENTION (Models/Entities/base_entity.py) and are the same in every database
    the migrations create. For SQLite, which reports the columns of a unique constraint instead of its name, the
    name is derived from the columns with the same convention.
    """
    original = error.orig

    # PostgreSQL drivers report the constraint name in a structured field.
    constraint_name = getattr(getattr(original, "diag", None), "constraint_name", None)
    if constraint_name:
        return str(constraint_name)

    message = str(original)
    for pattern in (_MYSQL_DUPLICATE_KEY, _MYSQL_CHECK, _MYSQL_CONSTRAINT, _SQLITE_CHECK):
        match = pattern.search(message)
        if match:
            return match.group(1)

    match = _SQLITE_UNIQUE.search(message)
    if match:
        qualified_columns = [column.strip() for column in match.group(1).split(",")]
        table_name = qualified_columns[0].split(".")[0]
        column_names = [column.split(".")[-1] for column in qualified_columns]
        return NAMING_CONVENTION["uq"] % {"table_name": table_name, "column_0_N_name": "_".join(column_names)}

    return None


def service_error_for(error: IntegrityError, *, conflict: str = DEFAULT_CONFLICT_MESSAGE,
                      conflicts: Optional[Mapping[str, str]] = None, restricted: Optional[str] = None,
                      missing: str = DEFAULT_MISSING_MESSAGE, failed: str = DEFAULT_FAILED_MESSAGE) -> ServiceError:
    """The domain error for a violation the database reported when saving (see the module documentation).

    * ``conflict``: message of a unique violation; ``conflicts`` gives messages for particular unique constraints.
    * ``restricted``: given for a delete, a foreign key violation means other rows still refer to the deleted row
      (DeleteRestrictedError with this message); otherwise it means a referenced row is gone (NotFoundError with
      ``missing``).
    * ``failed``: message of a violation that is neither (PersistenceError).
    """
    violation = integrity_violation(error)
    if violation.kind is ViolationKind.UNIQUE:
        return ConflictError((conflicts or {}).get(violation.constraint_name or "", conflict))
    if violation.kind is ViolationKind.FOREIGN_KEY:
        return DeleteRestrictedError(restricted) if restricted is not None else NotFoundError(missing)
    if violation.kind is ViolationKind.CHECK:
        return BusinessRuleError(CHECK_MESSAGES.get(violation.constraint_name or "", DEFAULT_RULE_MESSAGE))
    return PersistenceError(failed)


async def save_changes_async(unit_of_work: IUnitOfWork, *, conflict: str = DEFAULT_CONFLICT_MESSAGE,
                             conflicts: Optional[Mapping[str, str]] = None, restricted: Optional[str] = None,
                             missing: str = DEFAULT_MISSING_MESSAGE,
                             failed: str = DEFAULT_FAILED_MESSAGE) -> SaveChangesResult:
    """Persist what the service staged in the unit of work, in one transaction.

    The services check the rules they know about (unique values, records in use) before staging, but another
    operation can get in between, and the database enforces more rules: a violation reported when saving is raised
    as the matching domain error (service_error_for(); the arguments are its messages). A value the database cannot
    store is an InvalidInputError. The unit of work has rolled back by then; nothing was saved.
    """
    try:
        return await unit_of_work.save_changes_async()
    except IntegrityError as error:
        raise service_error_for(error, conflict=conflict, conflicts=conflicts, restricted=restricted,
                                missing=missing, failed=failed) from error
    except DataError as error:
        raise InvalidInputError(OUT_OF_RANGE_MESSAGE) from error


def validated(field_type: Any, value: Any, field_name: str) -> Any:
    """Validate a single value with one of the request field types (Models/Dtos/Request/base_request.py), e.g.
    Amount or AccountNumber, so values passed to a service outside a request model follow the same rules.

    Returns the normalised value (e.g. an Amount as a Decimal with two places); raises InvalidInputError. The message
    names the field and the rule, never the value given.
    """
    try:
        return _adapter(field_type).validate_python(value)
    except ValidationError as error:
        reason = error.errors()[0].get("msg", "invalid value") if error.errors() else "invalid value"
        raise InvalidInputError(f"Invalid {field_name}: {reason}") from None


def _violation_kind(original: Any) -> ViolationKind:
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    if sqlstate in _SQLSTATE_KINDS:
        return _SQLSTATE_KINDS[sqlstate]

    arguments = getattr(original, "args", ())
    if arguments and isinstance(arguments[0], int) and arguments[0] in _MYSQL_ERROR_KINDS:
        return _MYSQL_ERROR_KINDS[arguments[0]]

    message = str(original)
    for prefix, kind in _SQLITE_MESSAGE_KINDS.items():
        if prefix in message:
            return kind
    return ViolationKind.OTHER


_ADAPTERS: dict[int, TypeAdapter[Any]] = {}


def _adapter(field_type: Any) -> TypeAdapter[Any]:
    adapter = _ADAPTERS.get(id(field_type))
    if adapter is None:
        adapter = _ADAPTERS[id(field_type)] = TypeAdapter(field_type)
    return adapter
