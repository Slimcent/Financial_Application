import re
import unicodedata
from decimal import Decimal
from typing import Annotated, Any, Optional

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, Strict

# Database limits (see models/ and alembic/versions/)
MYSQL_INT_MAX = 2_147_483_647
NAME_MAX_LENGTH = 100            # Users.LastName / Users.FirstName, Staff.Position, Roles.Name
EMAIL_MAX_LENGTH = 254           # RFC 5321 limit (Users.Email column is 255)
ADDRESS_MAX_LENGTH = 255         # Customers.Address
ACCOUNT_TYPE_NAME_MAX_LENGTH = 50  # AccountTypes.Type
DESCRIPTION_MAX_LENGTH = 255     # Transactions.Description
SEARCH_TERM_MAX_LENGTH = 255     # longest searchable column (Users.Email)
ACCOUNT_NUMBER_LENGTH = 10       # Accounts.AccountNumber
AMOUNT_MAX_DIGITS = 10           # DECIMAL(10, 2)
AMOUNT_DECIMAL_PLACES = 2
MAX_AMOUNT = Decimal("99999999.99")  # largest value DECIMAL(10, 2) can hold
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_BYTES = 72          # bcrypt only uses the first 72 bytes

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50

_PERSON_NAME_PATTERN = re.compile(r"^[^\W\d_]+(?:(?:[ '’\-]|\. ?)[^\W\d_]+)*\.?$")
_EMAIL_PATTERN = re.compile(
    r"^(?=.{1,64}@)"
    r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)
_ACCOUNT_NUMBER_PATTERN = re.compile(rf"^[0-9]{{{ACCOUNT_NUMBER_LENGTH}}}$")
_TWO_PLACES = Decimal("0.01")


class BaseRequest(BaseModel):
    """Common configuration shared by every request model."""

    model_config = ConfigDict(
        extra="forbid",               # unknown / misspelled fields raise instead of being silently dropped
        frozen=True,                  # requests are not mutated after construction
        hide_input_in_errors=True,    # never echo submitted values (e.g. passwords) in error messages
    )


# ---------------------------------------------------------------------------
# Normalisers (run before type validation)
# ---------------------------------------------------------------------------

def _strip(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


def _strip_to_none(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _strip_and_lower(value: Any) -> Any:
    return value.strip().lower() if isinstance(value, str) else value


def _reject_inexact_amount(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("amount must be a number, not a boolean")
    if isinstance(value, float):
        raise ValueError("amount must be given as a Decimal, int or numeric string, not a float")
    return value


# ---------------------------------------------------------------------------
# Validators (run after type validation)
# ---------------------------------------------------------------------------

def _without_combining_marks(value: str) -> Optional[str]:
    """Drop combining marks that follow a letter (e.g. Devanagari/Tamil vowel signs); None if a mark is misplaced."""
    result = []
    follows_letter = False
    for char in value:
        category = unicodedata.category(char)
        if category.startswith("M"):
            if not follows_letter:
                return None
            continue
        result.append(char)
        follows_letter = category.startswith("L")
    return "".join(result)


def _validate_person_name(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    base_letters = _without_combining_marks(value)
    if base_letters is None or not _PERSON_NAME_PATTERN.match(base_letters):
        raise ValueError(
            "must start with a letter and contain only letters, single spaces, hyphens, apostrophes or periods"
        )
    return value


def _validate_email(value: str) -> str:
    if not _EMAIL_PATTERN.match(value):
        raise ValueError("must be a valid email address")
    return value


def _validate_account_number(value: str) -> str:
    if not _ACCOUNT_NUMBER_PATTERN.match(value):
        raise ValueError(f"must be exactly {ACCOUNT_NUMBER_LENGTH} digits")
    return value


def _validate_password(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"must not be longer than {PASSWORD_MAX_BYTES} bytes")
    return value


def _quantize_amount(value: Decimal) -> Decimal:
    return value.quantize(_TWO_PLACES)


# ---------------------------------------------------------------------------
# Reusable field types
# ---------------------------------------------------------------------------

# Note: in these types Strict()/Field(...) must come before BeforeValidator. Otherwise pydantic applies the
# constraints as a generic check after validation: string limits report "Value should have at most N items"
# instead of "String should have at most N characters", and the Decimal whole-digit check is dropped.

PositiveId = Annotated[int, Strict(), Field(gt=0, le=MYSQL_INT_MAX)]

PersonName = Annotated[
    str,
    Strict(),
    Field(min_length=1, max_length=NAME_MAX_LENGTH),
    BeforeValidator(_strip),
    AfterValidator(_validate_person_name),
]

EmailAddress = Annotated[
    str,
    Strict(),
    Field(min_length=3, max_length=EMAIL_MAX_LENGTH),
    BeforeValidator(_strip_and_lower),
    AfterValidator(_validate_email),
]

AccountNumber = Annotated[
    str,
    Strict(),
    BeforeValidator(_strip),
    AfterValidator(_validate_account_number),
]

# Use with Field(repr=False) on the model field so the value never appears in repr()/logs.
Password = Annotated[
    str,
    Strict(),
    Field(min_length=PASSWORD_MIN_LENGTH),
    AfterValidator(_validate_password),
]

Amount = Annotated[
    Decimal,
    Field(gt=0, le=MAX_AMOUNT, max_digits=AMOUNT_MAX_DIGITS, decimal_places=AMOUNT_DECIMAL_PLACES),
    BeforeValidator(_reject_inexact_amount),
    AfterValidator(_quantize_amount),
]


# Optional free text: surrounding whitespace removed, blank input becomes None.
Description = Annotated[
    Optional[Annotated[str, Strict(), Field(max_length=DESCRIPTION_MAX_LENGTH)]],
    BeforeValidator(_strip_to_none),
]

SearchTerm = Annotated[
    Optional[Annotated[str, Strict(), Field(max_length=SEARCH_TERM_MAX_LENGTH)]],
    BeforeValidator(_strip_to_none),
]

# Required free text: surrounding whitespace removed, must not be blank.
Address = Annotated[str, Strict(), Field(min_length=1, max_length=ADDRESS_MAX_LENGTH), BeforeValidator(_strip)]

Position = Annotated[str, Strict(), Field(min_length=1, max_length=NAME_MAX_LENGTH), BeforeValidator(_strip)]

RoleName = Annotated[str, Strict(), Field(min_length=1, max_length=NAME_MAX_LENGTH), BeforeValidator(_strip)]

AccountTypeName = Annotated[
    str, Strict(), Field(min_length=1, max_length=ACCOUNT_TYPE_NAME_MAX_LENGTH), BeforeValidator(_strip)
]
