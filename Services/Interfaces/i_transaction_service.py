"""Contract of the transaction service: funding accounts, transfers and transaction history.

Every method is given the caller's unit of work, which must be active (``async with``). Funding and transfers lock
the accounts involved, change the balances and record the transactions in one transaction. Amounts and balances
are Decimals. Errors are raised as the domain errors in Services/Exceptions; the unit of work then rolls back.
"""
import uuid
from abc import ABC, abstractmethod

from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Models.Dtos.Request.fund_account_request import FundAccountRequest
from Models.Dtos.Request.transaction_request import FundsTransferRequest, TransactionsRequest, UserTransactionsRequest
from Models.Dtos.Response.AccountResponse import AccountResponse
from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Response.paged_response import PagedResponse
from Models.Dtos.Response.transaction_response import TransactionsResponse


class ITransactionService(ABC):

    @abstractmethod
    async def fund_account(self, unit_of_work: IUnitOfWork, request: FundAccountRequest) -> AccountsResponse:
        """Deposit the request's amount into the customer's account and record it as a completed deposit (credit);
        returns the account with its new balance.

        Raises BusinessRuleError if the transaction type is not Deposit or the mode is not Credit, or if the
        customer or the account is not active; NotFoundError if the customer (request.customer_id, a Customers.Id)
        has no account with the request's account number.
        """

    @abstractmethod
    async def transfer_funds(self, unit_of_work: IUnitOfWork, request: FundsTransferRequest) -> AccountsResponse:
        """Move an amount from the sender's account to the receiver's and record the debit and the credit (sharing
        one transfer reference); returns the sender's account with its new balance.

        Raises NotFoundError if an account does not exist, BusinessRuleError if an account or its owner is not
        active, InsufficientFundsError if the sender's balance does not cover the amount.
        """

    @abstractmethod
    async def get_user_transactions(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> AccountResponse:
        """The transactions on a user's accounts (newest first) and the total balance of those accounts.

        Raises NotFoundError if the user does not exist.
        """

    @abstractmethod
    async def filter_user_transactions(self, unit_of_work: IUnitOfWork,
                                       request: UserTransactionsRequest) -> AccountResponse:
        """get_user_transactions() limited to the transactions that match the request's filters."""

    @abstractmethod
    async def get_all_transactions_paginated(self, unit_of_work: IUnitOfWork,
                                             request: TransactionsRequest) -> PagedResponse[TransactionsResponse]:
        """One page of the transactions that match the request's filters and search term, newest first; the page is
        read from the database together with the total number of matching transactions."""

    @abstractmethod
    async def get_all_transactions_non_paginated(self, unit_of_work: IUnitOfWork,
                                                 request: TransactionsRequest) -> list[TransactionsResponse]:
        """The most recent transactions (at most 15) that match the request's filters and search term, newest
        first. Not paged: the request's page and page size are ignored."""
