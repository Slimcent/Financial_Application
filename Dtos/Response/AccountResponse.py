from dataclasses import dataclass
from typing import List, Dict

from Dtos.Response import AccountsResponse
from Dtos.Response.transaction_response import TransactionsResponse


@dataclass
class AccountResponse:
    def __init__(
            self,
            user_id: int = None,
            customer_id: int = None,
            last_name: str = None,
            first_name: str = None,
            address: str = None,
            email: str = None,
            accounts: List[AccountsResponse] = None,
            transactions: List[TransactionsResponse] = None,
            balance: float = None,
            total_balance: float = None,
    ):
        self.user_id = user_id
        self.customer_id = customer_id
        self.last_name = last_name
        self.first_name = first_name
        self.email = email
        self.address = address
        self.accounts = accounts or []
        self.transactions = transactions or []
        self.balance = balance
        self.total_balance = total_balance

    def __repr__(self):
        return (
            f"AccountResponse(user_id={self.user_id!r}, "
            f"customer_id={self.customer_id!r}, "
            f"last_name={self.last_name!r}, "
            f"first_name={self.first_name!r}, "
            f"email={self.email!r}, "
            f"address={self.address!r}, "
            f"accounts={self.accounts!r}, "
            f"transactions={self.transactions!r}, "
            f"balance={self.balance!r}, "
            f"total_balance={self.total_balance!r})"
        )
