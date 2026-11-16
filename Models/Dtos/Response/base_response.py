import uuid
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Strict


class BaseResponse(BaseModel):
    """Common configuration shared by every response model."""

    model_config = ConfigDict(
        extra="forbid",  # a misspelled or unknown field raises instead of being silently dropped
    )


# ---------------------------------------------------------------------------
# Reusable field types
# ---------------------------------------------------------------------------

# Identifiers have exactly the type of their key column. GUID keys (Users, Customers, Staff, Accounts, Transactions):
# a UUID (from JSON, its text form). Integer keys (Roles, AccountTypes, TransactionTypes / Modes / Statuses): an int,
# not a bool, a float or text.
GuidId = Annotated[uuid.UUID, Strict()]
IntegerId = Annotated[int, Strict()]


def _float_to_decimal(value: Any) -> Any:
    # A float is taken by its shortest text form (0.1 -> Decimal("0.1"), not 0.1000000000000000055...).
    if isinstance(value, float):
        return Decimal(repr(value))
    return value


# Money: a Decimal, as the entities store it (DECIMAL columns). Decimals, ints, numeric text and floats are accepted;
# not-a-number, infinity and booleans are not.
Money = Annotated[Decimal, BeforeValidator(_float_to_decimal)]
