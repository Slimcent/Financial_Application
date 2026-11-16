from datetime import datetime
from typing import Optional

from Models.Dtos.Response.base_response import BaseResponse, GuidId, IntegerId, Money


class TransactionResponse(BaseResponse):
    """A transaction on one of a user's accounts."""

    account_id: GuidId
    account_number: str
    amount: Money
    account_type_id: IntegerId
    account_type: str
    transaction_type_id: IntegerId
    transaction_type: str
    transaction_mode_id: IntegerId
    transaction_mode: str
    transaction_status_id: IntegerId
    transaction_status: str
    transaction_date: datetime
    description: Optional[str] = None
    sender_id: Optional[GuidId] = None
    sender: Optional[str] = None


class TransactionsResponse(BaseResponse):
    """A transaction with the details of the account owner (for transaction lists across users)."""

    user_id: GuidId
    last_name: str
    first_name: str
    address: Optional[str] = None
    email: str
    account_id: GuidId
    account_number: str
    amount: Money
    account_type_id: IntegerId
    account_type: str
    transaction_type_id: IntegerId
    transaction_type: str
    transaction_mode_id: IntegerId
    transaction_mode: str
    transaction_status_id: IntegerId
    transaction_status: str
    transaction_date: datetime
    description: Optional[str] = None
    customer_id: Optional[GuidId] = None
    staff_id: Optional[GuidId] = None
    sender_id: Optional[GuidId] = None
    sender: Optional[str] = None
