from pydantic import BaseModel
from decimal import Decimal


class FundAccountRequest(BaseModel):
    customer_id: int
    account_number: str
    amount: Decimal
    transaction_type_id: int
    transaction_mode_id: int
