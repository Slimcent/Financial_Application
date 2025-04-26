from typing import List, Dict

from Dtos.Response import AccountsResponse


class AccountResponse:
    def __init__(
            self,
            user_id: int = None,
            customer_id: int = None,
            last_name: str = None,
            first_name: str = None,
            email: str = None,
            accounts: List[AccountsResponse] = None,
            balance: float = None,
            total_balance: float = None,
    ):
        self.user_id = user_id
        self.customer_id = customer_id
        self.last_name = last_name
        self.first_name = first_name
        self.email = email
        self.accounts = accounts or []
        self.balance = balance
        self.total_balance = total_balance
