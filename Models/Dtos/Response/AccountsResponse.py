from typing import Optional

from Models.Dtos.Response.base_response import BaseResponse, GuidId, IntegerId, Money


class AccountsResponse(BaseResponse):
    """One account. ``active`` is False once the account is deactivated."""

    account_id: GuidId
    account_number: str
    balance: Money
    account_type_id: IntegerId
    account_type: Optional[str] = None
    active: bool
