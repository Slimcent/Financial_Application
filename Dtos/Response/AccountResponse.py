from datetime import datetime
from typing import List, Dict


class AccountResponse:
    def __init__(
            self,
            user_id: int = None,
            staff_id: int = None,
            last_name: str = None,
            first_name: str = None,
            email: str = None,
            account_types: List[Dict[int, str]] = None,
            balance: str = None,
    ):
        self.user_id = user_id
        self.staff_id = staff_id
        self.last_name = last_name
        self.first_name = first_name
        self.email = email
        self.account_types = account_types or []
        self.balance = balance
