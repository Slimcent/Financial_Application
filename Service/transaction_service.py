from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from Dtos.Request.transaction_request import TransactionRequest
from Dtos.Response.AccountResponse import AccountResponse
from Dtos.Response.AccountsResponse import AccountsResponse
from Infrastructure.AppConstants import AppConstants
from Repository.transaction_repository import TransactionRepository
from Utility.exception_handler import wrap_errors
from database_orm_async import Database


class TransactionService:
    def __init__(self, transaction_repository: TransactionRepository):
        self.transaction_repository = transaction_repository
        self.constants = AppConstants
        self.db = Database()

    async def get_customer_account_details(self, customer_id: int, account_type_id: int) -> AccountResponse:
        print("Transaction service")
        account = await self.transaction_repository.get_customer_accounts(customer_id, account_type_id)

        if not account:
            raise ValueError("Account not found.")

        print("Done with repo")
        customer = account.customer
        user = customer.user

        account_response = AccountsResponse(
            account_id=account.Id,
            account_number=account.AccountNumber,
            balance=float(account.Balance),
            account_type=account.account_type.Type,
            account_type_id=account.AccountTypeId
        )

        print("Finished mapping")

        return AccountResponse(
            user_id=user.Id,
            customer_id=customer.Id,
            last_name=user.LastName,
            first_name=user.FirstName,
            email=user.Email,
            accounts=[account_response],
            balance=float(account.Balance)
        )

    async def get_customer_accounts_with_user_id(self, user_id: int) -> AccountResponse:
        customer = await self.transaction_repository.get_customer_accounts_with_user_id(user_id)

        if not customer:
            raise ValueError("Customer not found.")

        user = customer.user

        account_responses = [
            AccountsResponse(
                account_id=account.Id,
                account_number=account.AccountNumber,
                balance=float(account.Balance),
                account_type_id=account.AccountTypeId,
                account_type=account.account_type.Type
            )
            for account in customer.accounts
        ]

        total_balance = sum(account.Balance for account in customer.accounts)

        return AccountResponse(
            user_id=user.Id,
            customer_id=customer.Id,
            last_name=user.LastName,
            first_name=user.FirstName,
            email=user.Email,
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

        if not account.customer or not account.customer.user:
            print("Associated customer not found")

        if not account.customer.user:
            print("Associated user not found")

        if not account.customer.user.Id:
            print("User id can not be null")

        print(f"User id = {account.customer.user.Id}")

        try:
            async with self.db.get_session() as session:
                async with session.begin():

                    await self.transaction_repository.update_account_balance(account, amount, session=session)

                    transaction_request = TransactionRequest(
                        user_id=account.customer.UserId,
                        account_id=account.Id,
                        account_number=account.AccountNumber,
                        amount=amount,
                        transaction_type_id=self.constants.DepositTransactionTypeId,
                        transaction_mode_id=self.constants.CreditTransactionModeId,
                        transaction_status_id=self.constants.CompletedTransactionStatusId,
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

