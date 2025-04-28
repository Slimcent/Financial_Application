from datetime import datetime


class TransactionsResponse:
    def __init__(
            self,
            account_id: int,
            account_number: str,
            amount: float,
            account_type_id: int,
            account_type: str,
            transaction_type_id: int,
            transaction_type: str,
            transaction_mode_id: int,
            transaction_mode: str,
            transaction_status_id: int,
            transaction_status: str,
            transaction_date: datetime,
            description: None,
            sender_id: int = None,
            sender: str = None,
    ):

        self.account_id = account_id
        self.account_number = account_number
        self.amount = amount
        self.account_type_id = account_type_id
        self.account_type = account_type
        self.transaction_type_id = transaction_type_id
        self.transaction_type = transaction_type
        self.transaction_mode_id = transaction_mode_id
        self.transaction_mode = transaction_mode
        self.transaction_status_id = transaction_status_id
        self.transaction_status = transaction_status
        self.transaction_date = transaction_date
        self.description = description
        self.sender_id = sender_id
        self.sender = sender

    def __repr__(self):
        return (
            f"TransactionsResponse("
            f"account_id={self.account_id}, "
            f"account_number='{self.account_number}', "
            f"balance={self.amount}, "
            f"account_type_id={self.account_type_id}, "
            f"transaction_type_id='{self.transaction_type_id}' "
            f"transaction_type='{self.transaction_type}' "
            f"transaction_mode_id='{self.transaction_mode_id}' "
            f"transaction_mode='{self.transaction_mode}' "
            f"transaction_status_id='{self.transaction_status_id}' "
            f"transaction_status='{self.transaction_status}' "
            f"transaction_date='{self.transaction_date}' "
            f"description='{self.description}' "
            f"sender_id='{self.sender_id}' "
            f"sender='{self.sender}'"
            f")"
        )
