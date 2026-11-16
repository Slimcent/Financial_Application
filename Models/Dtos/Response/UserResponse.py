from datetime import datetime
from typing import List, Optional

from pydantic import Field

from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Response.base_response import BaseResponse, GuidId, IntegerId


class UserResponse(BaseResponse):
    """A user; with the customer details (customer_id, address, accounts) or the staff details (staff_id,
    position) when the user is a customer or a staff member."""

    user_id: Optional[GuidId] = None
    customer_id: Optional[GuidId] = None
    staff_id: Optional[GuidId] = None
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    position: Optional[str] = None
    role_id: Optional[IntegerId] = None
    role_name: Optional[str] = None
    accounts: List[AccountsResponse] = Field(default_factory=list)
    active: Optional[bool] = None
    created_at: Optional[datetime] = None
