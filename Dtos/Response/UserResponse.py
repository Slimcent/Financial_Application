from typing import List
from datetime import datetime
from Dtos.Response import AccountsResponse


class UserResponse:
    def __init__(
            self,
            user_id: int = None,
            customer_id: int = None,
            staff_id: int = None,
            last_name: str = None,
            first_name: str = None,
            email: str = None,
            address: str = None,
            position: str = None,
            role_id: str = None,
            role_name: str = None,
            accounts: List[AccountsResponse] = None,
            active: bool = None,
            created_at: datetime = None
    ):
        self.user_id = user_id
        self.customer_id = customer_id
        self.staff_id = staff_id
        self.last_name = last_name
        self.first_name = first_name
        self.email = email
        self.address = address
        self.position = position
        self.role_id = role_id
        self.role_name = role_name
        self.accounts = accounts or []
        self.active = active
        self.created_at = created_at
