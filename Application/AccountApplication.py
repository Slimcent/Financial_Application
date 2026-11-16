import uuid
from Models.Dtos.Response.AccountResponse import AccountResponse
from Data.Interfaces.i_unit_of_work import UnitOfWorkFactory
from Infrastructure.Logging.logger import logger
from typing import Optional, List
from Services.Exceptions.domain_exceptions import ServiceError
from Services.Interfaces.i_account_service import IAccountService


def _convert_account_response_to_dict(account_response: AccountResponse) -> dict:
    return {
        "user_id": account_response.user_id,
        "customer_id": account_response.customer_id,
        "last_name": account_response.last_name,
        "first_name": account_response.first_name,
        "email": account_response.email,
        "accounts": [vars(account) for account in account_response.accounts],
        "balance": account_response.balance,
        "total_balance": account_response.total_balance,
    }


class AccountApplication:
    def __init__(self, unit_of_work_factory: UnitOfWorkFactory, account_service: IAccountService):
        self.unit_of_work_factory = unit_of_work_factory
        self.account_service = account_service

    async def get_all_customer_accounts(self) -> List[dict]:
        logger.info("Getting all customer accounts...")

        async with self.unit_of_work_factory() as unit_of_work:
            accounts = await self.account_service.get_all_customer_accounts(unit_of_work)

        if not accounts:
            logger.info("No customer accounts found.")
            return []

        account_responses = [
            {
                "user_id": account.user_id,
                "first_name": account.first_name,
                "last_name": account.last_name,
                "email": account.email,
                "accounts": [vars(item) for item in account.accounts],
                "total_balance": account.total_balance,
            }
            for account in accounts
        ]

        return account_responses

    async def get_customer_account_details(self, user_id: uuid.UUID, account_type_id: int) -> Optional[dict]:
        logger.info(f"Getting account details for UserId: {user_id} and AccountTypeId: {account_type_id}")

        try:
            async with self.unit_of_work_factory() as unit_of_work:
                account_response = await self.account_service.get_customer_account_details(unit_of_work, user_id,
                                                                                            account_type_id)
        except ServiceError as error:
            logger.error(error.message)
            return None

        logger.info("Mapping retrieved account details to account response")
        return _convert_account_response_to_dict(account_response)
