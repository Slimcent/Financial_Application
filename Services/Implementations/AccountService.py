import uuid

from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Infrastructure.Logging.logger import logger
from Models.Dtos.Request.base_request import AccountNumber
from Models.Dtos.Response.AccountResponse import AccountResponse
from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Entities import Account, User
from Services.Exceptions.domain_exceptions import NotFoundError
from Services.Extensions.exception_handler import validated
from Services.Extensions.response_mappers import to_account_response, to_accounts_response
from Services.Interfaces.i_account_service import IAccountService

# What the account responses read: the owner's customer record and every account with its account type.
USER_ACCOUNTS_INCLUDES = ("customer", "accounts.account_type")


class AccountService(IAccountService):

    async def get_all_customer_accounts(self, unit_of_work: IUnitOfWork) -> list[AccountResponse]:
        statement = (unit_of_work.users.query()
                     .where(User.customer.has())
                     .order_by(User.LastName, User.FirstName))
        users = await unit_of_work.users.get_range_async(statement, includes=USER_ACCOUNTS_INCLUDES)

        logger.info(f"Got {len(users)} customers with their accounts.")
        return [to_account_response(user, user.accounts, customer=user.customer) for user in users]

    async def get_customer_account_details(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID,
                                           account_type_id: int) -> AccountResponse:
        account = await unit_of_work.accounts.get_single_async(
            Account.UserId == user_id, Account.AccountTypeId == account_type_id,
            includes=["user.customer", "account_type"])
        if account is None:
            raise NotFoundError(f"User {user_id} has no account of account type {account_type_id}.")

        user = account.user
        return to_account_response(user, [account], customer=user.customer, balance=account.Balance)

    async def get_customer_accounts_with_user_id(self, unit_of_work: IUnitOfWork,
                                                 user_id: uuid.UUID) -> AccountResponse:
        user = await unit_of_work.users.get_by_id_async(user_id, includes=USER_ACCOUNTS_INCLUDES)
        if user is None:
            raise NotFoundError(f"User with Id {user_id} does not exist.")

        return to_account_response(user, user.accounts, customer=user.customer)

    async def get_account_details_by_account_number(self, unit_of_work: IUnitOfWork,
                                                    account_number: str) -> AccountsResponse:
        account_number = validated(AccountNumber, account_number, "account number")

        account = await unit_of_work.accounts.get_single_async(Account.AccountNumber == account_number,
                                                               includes=["account_type"])
        if account is None:
            raise NotFoundError("The account does not exist.")

        return to_accounts_response(account)
