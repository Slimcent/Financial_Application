from typing import Optional

from Models.Dtos.Response.base_response import BaseResponse, GuidId, IntegerId, Money


class LoginResponse(BaseResponse):
    user_id: GuidId
    last_name: str
    first_name: str
    email: str
    role_id: IntegerId
    role_name: str
    # Customers have an account (type and balance), staff have a position.
    account_type_id: Optional[IntegerId] = None
    account_type: Optional[str] = None
    balance: Optional[Money] = None
    position: Optional[str] = None
