from typing import Optional

from Dtos.Request.pagination_request import PaginationRequest


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
            sender_id: Optional[int] = None,
            description: Optional[str] = None
    ):
        self.user_id = user_id
        self.sender_id = sender_id
        self.account_id = account_id
        self.account_number = account_number
        self.amount = amount
        self.transaction_type_id = transaction_type_id
        self.transaction_mode_id = transaction_mode_id
        self.transaction_status_id = transaction_status_id
        self.description = description


class UserTransactionsRequest:
    def __init__(
            self,
            user_id: Optional[int] = None,
            sender_id: Optional[int] = None,
            account_type_id: Optional[int] = None,
            transaction_type_id: Optional[int] = None,
            transaction_mode_id: Optional[int] = None,
            account_number: Optional[str] = None,
            transaction_status_id: Optional[int] = None,
    ):
        self.user_id = user_id
        self.sender_id = sender_id
        self.account_type_id = account_type_id
        self.transaction_type_id = transaction_type_id
        self.transaction_mode_id = transaction_mode_id
        self.account_number = account_number
        self.transaction_status_id = transaction_status_id


class TransactionsRequest(PaginationRequest):
    def __init__(
        self,
        user_id: Optional[int] = None,
        sender_id: Optional[int] = None,
        account_type_id: Optional[int] = None,
        transaction_type_id: Optional[int] = None,
        transaction_mode_id: Optional[int] = None,
        account_number: Optional[str] = None,
        transaction_status_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 10,
        search_term: Optional[str] = None,
    ):
        super().__init__(page, page_size, search_term)

        self.user_id = user_id
        self.sender_id = sender_id
        self.account_type_id = account_type_id
        self.transaction_type_id = transaction_type_id
        self.transaction_mode_id = transaction_mode_id
        self.account_number = account_number
        self.transaction_status_id = transaction_status_id
