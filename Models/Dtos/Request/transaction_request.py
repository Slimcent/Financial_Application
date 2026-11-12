from typing import Optional

from pydantic import model_validator

from Models.Dtos.Request.base_request import AccountNumber, Amount, BaseRequest, Description, GuidId, PositiveId
from Models.Dtos.Request.pagination_request import PaginationRequest


class TransactionRequest(BaseRequest):
    user_id: GuidId
    account_id: GuidId
    account_number: AccountNumber
    amount: Amount
    transaction_type_id: PositiveId
    transaction_mode_id: PositiveId
    transaction_status_id: PositiveId
    sender_id: Optional[GuidId] = None
    description: Description = None


class UserTransactionsRequest(BaseRequest):
    user_id: GuidId
    sender_id: Optional[GuidId] = None
    account_type_id: Optional[PositiveId] = None
    transaction_type_id: Optional[PositiveId] = None
    transaction_mode_id: Optional[PositiveId] = None
    account_number: Optional[AccountNumber] = None
    transaction_status_id: Optional[PositiveId] = None


class TransactionsRequest(PaginationRequest):
    user_id: Optional[GuidId] = None
    sender_id: Optional[GuidId] = None
    account_type_id: Optional[PositiveId] = None
    transaction_type_id: Optional[PositiveId] = None
    transaction_mode_id: Optional[PositiveId] = None
    account_number: Optional[AccountNumber] = None
    transaction_status_id: Optional[PositiveId] = None


class FundsTransferRequest(BaseRequest):
    amount: Amount
    sender_account_number: AccountNumber
    receiver_account_number: AccountNumber
    description: Description = None

    @model_validator(mode="after")
    def _check_distinct_accounts(self) -> "FundsTransferRequest":
        if self.sender_account_number == self.receiver_account_number:
            raise ValueError("sender and receiver account numbers must be different")
        return self
