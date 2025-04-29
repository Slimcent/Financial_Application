from datetime import datetime


class TransactionResponse:
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


class TransactionsResponse:
    def __init__(
            self,
            user_id: int,
            last_name: str,
            first_name: str,
            address: str,
            email: str,
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
            customer_id: int = None,
            staff_id: int = None,
            sender_id: int = None,
            sender: str = None,
    ):
        self.user_id = user_id
        self.customer_id = customer_id
        self.staff_id = staff_id
        self.last_name = last_name
        self.first_name = first_name
        self.email = email
        self.address = address
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
            f"user_id={self.user_id}, "
            f"customer_id={self.customer_id}, "
            f"staff_id={self.staff_id}, "
            f"last_name={self.last_name}, "
            f"first_name={self.first_name}, "
            f"email={self.email}, "
            f"address={self.address}, "
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
