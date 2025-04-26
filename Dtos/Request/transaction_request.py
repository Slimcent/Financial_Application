from typing import Optional


class TransactionRequest:
    def __init__(
            self,
            user_id: int,
            account_id: int,
            account_number: str,
            amount: float,
            transaction_type_id: int,
            transaction_mode_id: int,
            transaction_status_id: int,
            description: Optional[str] = None
    ):
        self.user_id = user_id
        self.account_id = account_id
        self.account_number = account_number
        self.amount = amount
        self.transaction_type_id = transaction_type_id
        self.transaction_mode_id = transaction_mode_id
        self.transaction_status_id = transaction_status_id
        self.description = description
