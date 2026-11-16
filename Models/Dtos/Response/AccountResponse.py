from typing import List, Optional

from pydantic import Field

from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Response.base_response import BaseResponse, GuidId, Money
from Models.Dtos.Response.transaction_response import TransactionResponse


class AccountResponse(BaseResponse):
    """A user (the account holder) with accounts and / or transactions. ``active`` is whether the account holder is
    active (each account has its own ``active`` as well); ``balance`` is the balance of the one account the response
    is about (when there is one); ``total_balance`` is the sum of the balances of the user's accounts."""

    user_id: Optional[GuidId] = None
    customer_id: Optional[GuidId] = None
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    active: Optional[bool] = None
    accounts: List[AccountsResponse] = Field(default_factory=list)
    transactions: List[TransactionResponse] = Field(default_factory=list)
    balance: Optional[Money] = None
    total_balance: Optional[Money] = None
