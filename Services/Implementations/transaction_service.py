import uuid
from collections.abc import Sequence
from typing import Any, Union

from sqlalchemy import or_

from Data.Interfaces.i_repository import Criterion
from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Infrastructure.Logging.logger import logger
from Models.Constants.AppConstants import AppConstants
from Models.Dtos.Request.fund_account_request import FundAccountRequest
from Models.Dtos.Request.transaction_request import FundsTransferRequest, TransactionsRequest, UserTransactionsRequest
from Models.Dtos.Response.AccountResponse import AccountResponse
from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Response.paged_response import PagedResponse
from Models.Dtos.Response.transaction_response import TransactionsResponse
from Models.Entities import Account, Customer, Transaction, User
from Models.Entities.column_types import uuid7
from Services.Exceptions.domain_exceptions import BusinessRuleError, InsufficientFundsError, NotFoundError
from Services.Extensions.exception_handler import save_changes_async
from Services.Extensions.response_mappers import (TRANSACTION_INCLUDES, TRANSACTIONS_INCLUDES, to_accounts_response,
                                                  to_transaction_response, to_transactions_response)
from Services.Interfaces.i_transaction_service import ITransactionService

# Newest first. Transactions recorded at the same instant are ordered by their (time-ordered) Id, so the order, and
# with it every page and the most recent transactions, is stable.
NEWEST_FIRST = (Transaction.TransactionDate.desc(), Transaction.Id.desc())

# get_all_transactions_non_paginated() returns at most this many transactions: the most recent ones.
RECENT_TRANSACTIONS_LIMIT = 15


class TransactionService(ITransactionService):
    def __init__(self):
        self.constants = AppConstants

    async def fund_account(self, unit_of_work: IUnitOfWork, request: FundAccountRequest) -> AccountsResponse:
        if request.transaction_type_id != self.constants.DepositTransactionTypeId:
            raise BusinessRuleError("An account can only be funded with a deposit transaction.")
        if request.transaction_mode_id != self.constants.CreditTransactionModeId:
            raise BusinessRuleError("Funding an account credits it: the transaction mode must be credit.")

        # The account must belong to the customer in the request. The row stays locked until the unit of work
        # saves, so no other operation changes the balance meanwhile.
        account = await unit_of_work.accounts.get_single_async(
            Account.AccountNumber == request.account_number,
            Account.user.has(User.customer.has(Customer.Id == request.customer_id)),
            includes=["user", "account_type"], for_update=True)
        if account is None:
            raise NotFoundError(f"Customer {request.customer_id} has no account with this account number.")
        if not account.user.Active:
            raise BusinessRuleError("The owner of the account is not active.")
        if not account.Active:
            raise BusinessRuleError("The account is not active.")

        unit_of_work.accounts.update_single(account, {"Balance": account.Balance + request.amount})
        unit_of_work.transactions.add_single(Transaction(
            AccountId=account.Id,
            UserId=account.UserId,
            TransactionTypeId=request.transaction_type_id,
            TransactionModeId=request.transaction_mode_id,
            TransactionStatusId=self.constants.CompletedTransactionStatusId,
            Amount=request.amount,
            SenderId=account.UserId,
            Description=request.description,
        ))
        # One transaction: the new balance and the transaction row are saved together, and the lock is released.
        await save_changes_async(unit_of_work, failed="The account could not be funded.")

        logger.info(f"Funded account {account.Id} with {request.amount}")
        return to_accounts_response(account)

    async def transfer_funds(self, unit_of_work: IUnitOfWork, request: FundsTransferRequest) -> AccountsResponse:
        # Both rows are locked by one query in primary key order: concurrent transfers between the same accounts
        # always lock in the same order, so they wait for each other instead of deadlocking.
        accounts = await unit_of_work.accounts.get_range_async(
            Account.AccountNumber.in_([request.sender_account_number, request.receiver_account_number]),
            includes=["user", "account_type"], order_by=[Account.Id], for_update=True)
        by_number = {account.AccountNumber: account for account in accounts}

        sender = by_number.get(request.sender_account_number)
        if sender is None:
            raise NotFoundError("The sender account does not exist.")
        receiver = by_number.get(request.receiver_account_number)
        if receiver is None:
            raise NotFoundError("The receiver account does not exist.")
        if sender.Id == receiver.Id:
            raise BusinessRuleError("You cannot transfer money to the same account.")
        for side, account in (("sender", sender), ("receiver", receiver)):
            if not account.user.Active:
                raise BusinessRuleError(f"The owner of the {side} account is not active.")
            if not account.Active:
                raise BusinessRuleError(f"The {side} account is not active.")
        if sender.Balance < request.amount:
            raise InsufficientFundsError("The sender account has insufficient funds for this transfer.")

        unit_of_work.accounts.update_single(sender, {"Balance": sender.Balance - request.amount})
        unit_of_work.accounts.update_single(receiver, {"Balance": receiver.Balance + request.amount})

        transfer_reference = uuid7()  # links the debit and the credit row of this transfer
        unit_of_work.transactions.add_range([
            self._transfer_row(sender, sender, request, self.constants.DebitTransactionModeId, transfer_reference),
            self._transfer_row(receiver, sender, request, self.constants.CreditTransactionModeId, transfer_reference),
        ])
        # One transaction: both balances and both transaction rows are saved together, and the locks are released.
        await save_changes_async(unit_of_work, failed="The transfer could not be completed.")

        logger.info(f"Transferred {request.amount} from account {sender.Id} to account {receiver.Id} "
                    f"(reference {transfer_reference})")
        return to_accounts_response(sender)

    async def get_user_transactions(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> AccountResponse:
        return await self._user_transactions(unit_of_work, user_id, [])

    async def filter_user_transactions(self, unit_of_work: IUnitOfWork,
                                       request: UserTransactionsRequest) -> AccountResponse:
        return await self._user_transactions(unit_of_work, request.user_id, _filter_criteria(request))

    async def get_all_transactions_paginated(self, unit_of_work: IUnitOfWork,
                                             request: TransactionsRequest) -> PagedResponse[TransactionsResponse]:
        page = await unit_of_work.transactions.get_range_async(
            *_transactions_criteria(request), page=request.page, page_size=request.page_size,
            includes=TRANSACTIONS_INCLUDES, order_by=NEWEST_FIRST)

        return PagedResponse[TransactionsResponse](
            total_count=page.total_count, page=page.page, page_size=page.page_size,
            items=[to_transactions_response(transaction) for transaction in page.items])

    async def get_all_transactions_non_paginated(self, unit_of_work: IUnitOfWork,
                                                 request: TransactionsRequest) -> list[TransactionsResponse]:
        # Not paged: only the most recent transactions that match.
        transactions = await unit_of_work.transactions.get_range_async(
            *_transactions_criteria(request), includes=TRANSACTIONS_INCLUDES, order_by=NEWEST_FIRST,
            take=RECENT_TRANSACTIONS_LIMIT)

        return [to_transactions_response(transaction) for transaction in transactions]

    async def _user_transactions(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID,
                                 criteria: Sequence[Criterion]) -> AccountResponse:
        user = await unit_of_work.users.get_by_id_async(user_id, includes=["customer"])
        if user is None:
            raise NotFoundError(f"User with Id {user_id} does not exist.")

        transactions = await unit_of_work.transactions.get_range_async(
            Transaction.UserId == user_id, *criteria, includes=TRANSACTION_INCLUDES, order_by=NEWEST_FIRST)
        total_balance = await unit_of_work.accounts.sum_async(Account.Balance, Account.UserId == user_id)

        customer = user.customer
        return AccountResponse(
            user_id=user.Id,
            customer_id=customer.Id if customer is not None else None,
            last_name=user.LastName,
            first_name=user.FirstName,
            address=customer.Address if customer is not None else None,
            email=user.Email,
            active=user.Active,
            transactions=[to_transaction_response(transaction) for transaction in transactions],
            total_balance=total_balance,
        )

    def _transfer_row(self, account: Account, sender: Account, request: FundsTransferRequest, mode_id: int,
                      transfer_reference: uuid.UUID) -> Transaction:
        return Transaction(
            AccountId=account.Id,
            UserId=account.UserId,
            TransactionTypeId=self.constants.TransferTransactionTypeId,
            TransactionModeId=mode_id,
            TransactionStatusId=self.constants.CompletedTransactionStatusId,
            Amount=request.amount,
            SenderId=sender.UserId,
            Description=request.description,
            TransferReference=transfer_reference,
        )


def _filter_criteria(request: Union[UserTransactionsRequest, TransactionsRequest]) -> list[Any]:
    """SQL conditions for the filters both transaction requests have."""
    criteria: list[Any] = []
    if request.sender_id is not None:
        criteria.append(Transaction.SenderId == request.sender_id)
    if request.account_type_id is not None:
        criteria.append(Transaction.account.has(Account.AccountTypeId == request.account_type_id))
    if request.transaction_type_id is not None:
        criteria.append(Transaction.TransactionTypeId == request.transaction_type_id)
    if request.transaction_mode_id is not None:
        criteria.append(Transaction.TransactionModeId == request.transaction_mode_id)
    if request.transaction_status_id is not None:
        criteria.append(Transaction.TransactionStatusId == request.transaction_status_id)
    if request.account_number is not None:
        criteria.append(Transaction.account.has(Account.AccountNumber == request.account_number))
    return criteria


def _transactions_criteria(request: TransactionsRequest) -> list[Any]:
    """SQL conditions for TransactionsRequest: its filters, the account owner and the search term."""
    criteria = _filter_criteria(request)
    if request.user_id is not None:
        criteria.append(Transaction.UserId == request.user_id)
    if request.search_term is not None:
        term = request.search_term
        # autoescape: % and _ in the search term are matched literally, not as wildcards.
        criteria.append(or_(
            Transaction.user.has(or_(User.FirstName.icontains(term, autoescape=True),
                                     User.LastName.icontains(term, autoescape=True),
                                     User.Email.icontains(term, autoescape=True))),
            Transaction.account.has(Account.AccountNumber.icontains(term, autoescape=True)),
        ))
    return criteria
