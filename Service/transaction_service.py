from typing import Optional, List

from sqlalchemy.exc import SQLAlchemyError

from Dtos.Request.transaction_request import TransactionRequest, TransactionsRequest
from Dtos.Request.transaction_request import UserTransactionsRequest
from Dtos.Response.AccountResponse import AccountResponse
from Dtos.Response.AccountsResponse import AccountsResponse
from Dtos.Response.paged_response import PagedResponse
from Dtos.Response.transaction_response import TransactionResponse, TransactionsResponse
from Infrastructure.AppConstants import AppConstants
from Repository.transaction_repository import TransactionRepository
from Utility.exception_handler import wrap_errors
from Utility.pagination import Pagination
from database_orm_async import Database
from models.transaction import Transaction
from models.user import User


class TransactionService:
    def __init__(self, transaction_repository: TransactionRepository):
        self.transaction_repository = transaction_repository
        self.constants = AppConstants
        self.db = Database()

    async def get_customer_account(self, user_id: int, account_type_id: int) -> AccountResponse:
        print("Transaction service")
        account = await self.transaction_repository.get_customer_account(user_id, account_type_id)

        if not account:
            raise ValueError("Account not found.")

        user = account.user
        customer = account.user.customer

        account_response = AccountsResponse(
            account_id=account.Id,
            account_number=account.AccountNumber,
            balance=float(account.Balance),
            account_type_id=account.account_type.Id,
            account_type=account.account_type.Type
        )

        print("Finished mapping")

        return AccountResponse(
            user_id=user.Id,
            customer_id=customer.Id,
            last_name=user.LastName,
            first_name=user.FirstName,
            email=user.Email,
            accounts=[account_response],
            balance=float(account.Balance),
            total_balance=float(account.Balance)
        )

    async def get_customer_accounts_with_user_id(self, user_id: int) -> AccountResponse:
        user: User = await self.transaction_repository.get_customer_accounts_with_user_id(user_id)

        if not user:
            raise ValueError("user not found.")

        account_responses = [
            AccountsResponse(
                account_id=account.Id,
                account_number=account.AccountNumber,
                balance=float(account.Balance),
                account_type_id=account.AccountTypeId,
                account_type=account.account_type.Type
            )
            for account in user.accounts
        ]

        total_balance = sum(account.Balance for account in user.accounts)

        return AccountResponse(
            user_id=user.Id,
            customer_id=user.customer.Id,
            last_name=user.LastName,
            first_name=user.FirstName,
            email=user.Email,
            address=user.customer.Address,
            accounts=account_responses,
            total_balance=total_balance
        )

    async def get_account_details_by_account_number(self, account_number: str) -> Optional[AccountsResponse]:
        account = await self.transaction_repository.get_account_by_account_number(account_number)
        if account:
            return AccountsResponse(
                account_id=account.Id,
                account_number=account.AccountNumber,
                balance=account.Balance,
                account_type_id=account.AccountTypeId,
                account_type=account.account_type.Type
            )
        return None

    @wrap_errors
    async def fund_account(self, account_number: str, amount: float = 0.0, description: str = None) -> AccountsResponse:
        if amount <= 0:
            print("Amount must be greater than zero")

        if not account_number:
            print("Account number is required")

        account = await self.transaction_repository.get_account_by_account_number(account_number)
        if not account:
            print(f"Account with number {account_number} does not exist")

        if not account.user:
            print("Associated user not found")

        if not account.user.Id:
            print("User id can not be null")

        print(f"User id = {account.user.Id}")

        try:
            async with self.db.get_session() as session:
                async with session.begin():
                    await self.transaction_repository.update_account_balance(account, amount, session=session)

                    transaction_request = TransactionRequest(
                        user_id=account.UserId,
                        account_id=account.Id,
                        account_number=account.AccountNumber,
                        amount=amount,
                        transaction_type_id=self.constants.DepositTransactionTypeId,
                        transaction_mode_id=self.constants.CreditTransactionModeId,
                        transaction_status_id=self.constants.CompletedTransactionStatusId,
                        sender_id=account.UserId,
                        description=description
                    )

                    await self.transaction_repository.create_transaction(transaction_request, session=session)

            return AccountsResponse(
                account_id=account.Id,
                account_number=account.AccountNumber,
                balance=account.Balance,
                account_type_id=account.AccountTypeId,
                account_type=account.account_type.Type
            )

        except TypeError as e:
            raise ValueError("Failed to create transaction — please check your request structure.") from e

        except SQLAlchemyError as e:
            raise ValueError("Database operation failed") from e

        except Exception as e:
            raise ValueError(f"Unexpected error: {str(e)}") from e

    async def get_user_transactions(self, user_id: int) -> AccountResponse:
        user: User = await self.transaction_repository.get_user_transactions(user_id)

        account_response = await map_user_transactions(user)

        return account_response

    async def filter_user_transactions(self, request: UserTransactionsRequest) -> AccountResponse:
        user: User = await self.transaction_repository.get_user_transactions(request.user_id)

        user = await filter_transactions(user, request)

        account_response = await map_user_transactions(user)

        return account_response

    async def get_all_transactions_paginated(self, request: TransactionsRequest) -> PagedResponse[TransactionsResponse]:
        transactions = await self.transaction_repository.get_all_transactions(request)

        print("finished repo query")

        response_list: List[TransactionsResponse] = []

        for transaction in transactions:
            user = transaction.user
            account = transaction.account
            customer = getattr(user, "customer", None)
            staff = getattr(user, "staff", None)

            response = TransactionsResponse(
                user_id=user.Id,
                first_name=user.FirstName,
                last_name=user.LastName,
                email=user.Email,
                address=user.customer.Address if customer else None,
                customer_id=customer.Id if customer else None,
                staff_id=staff.id if staff else None,
                account_id=account.Id,
                account_number=account.AccountNumber,
                amount=transaction.Amount,
                account_type_id=account.account_type.Id,
                account_type=account.account_type.Type if account.account_type else None,
                transaction_type_id=transaction.TransactionTypeId,
                transaction_type=transaction.transaction_type.Name if transaction.transaction_type else None,
                transaction_mode_id=transaction.TransactionModeId,
                transaction_mode=transaction.transaction_mode.Name if transaction.transaction_mode else None,
                transaction_status_id=transaction.TransactionStatusId,
                transaction_status=transaction.transaction_status.Name if transaction.transaction_status else None,
                transaction_date=transaction.TransactionDate,
                description=transaction.Description,
                sender_id=transaction.SenderId,
                sender=f"{transaction.sender.FirstName} {transaction.sender.LastName}" if transaction.sender else None
            )

            response_list.append(response)

        return Pagination.paginate(request.page, request.page_size, response_list)


async def filter_transactions(user: User, request: UserTransactionsRequest) -> User:
    if request.account_type_id is not None:
        user.transactions = [
            transaction for transaction in user.transactions
            if transaction.account.account_type.Id == request.account_type_id
        ]

    if request.transaction_type_id is not None:
        user.transactions = [
            transaction for transaction in user.transactions
            if transaction.transaction_type.Id == request.transaction_type_id
        ]

    if request.transaction_mode_id is not None:
        user.transactions = [
            transaction for transaction in user.transactions
            if transaction.transaction_mode.Id == request.transaction_mode_id
        ]

    if request.account_number is not None:
        user.transactions = [
            transaction for transaction in user.transactions
            if transaction.account.AccountNumber == request.account_number
        ]

    if request.transaction_status_id is not None:
        user.transactions = [
            transaction for transaction in user.transactions
            if transaction.transaction_status.Id == request.transaction_status_id
        ]

    return user


async def map_user_transactions(user: User) -> AccountResponse:
    transactions_responses: List[TransactionResponse] = []
    total_balance = 0.0

    for transaction in user.transactions:
        account = transaction.account
        account_type = account.account_type
        transaction_type = transaction.transaction_type
        transaction_mode = transaction.transaction_mode
        transaction_status = transaction.transaction_status

        total_balance += float(transaction.Amount)

        transactions_responses.append(
            TransactionResponse(
                account_id=account.Id,
                account_number=account.AccountNumber,
                amount=float(transaction.Amount),
                account_type_id=account_type.Id,
                account_type=account_type.Type,
                transaction_type_id=transaction_type.Id,
                transaction_type=transaction_type.Name,
                transaction_mode_id=transaction_mode.Id,
                transaction_mode=transaction_mode.Name,
                transaction_status_id=transaction_status.Id,
                transaction_status=transaction_status.Name,
                transaction_date=transaction.TransactionDate,
                description=transaction.Description,
            )
        )

    customer = user.customer
    account_response = AccountResponse(
        user_id=user.Id,
        customer_id=customer.Id if customer else None,
        last_name=user.LastName,
        first_name=user.FirstName,
        email=user.Email,
        address=customer.Address if customer else None,
        transactions=transactions_responses,
        total_balance=total_balance
    )

    return account_response
