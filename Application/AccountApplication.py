from Dtos.Response.AccountResponse import AccountResponse
from database_connection import DatabaseConnection
from Repository.account_repository import AccountRepository
from logger import logger
from typing import Any, Optional, List
from Service.AccountService import AccountService


def _convert_account_response_to_dict(account_response: AccountResponse) -> dict:
    return {
        "user_id": account_response.user_id,
        "last_name": account_response.last_name,
        "first_name": account_response.first_name,
        "email": account_response.email,
        "account_type_id": account_response.account_type_id,
        "account_type": account_response.account_type,
        "account_number": account_response.account_number,
        "balance": account_response.balance,
        "account_types": account_response.account_types
    }


class AccountApplication:
    def __init__(self, db_connection: DatabaseConnection):
        self.account_repository = AccountRepository(db_connection)
        self.account_service = AccountService(self.account_repository)

    async def get_all_customer_accounts(self) -> Optional[List[dict]]:
        logger.info("Getting all customer accounts...")

        accounts = await self.account_service.get_all_customer_accounts()

        if accounts is None:
            logger.error("Failed to get customer accounts.")
            return None

        if not accounts:
            logger.info("No customer accounts found.")
            return []

        account_responses = [
            {
                "user_id": account.user_id,
                "first_name": account.first_name,
                "last_name": account.last_name,
                "email": account.email,
                "account_types": account.account_types,
            }
            for account in accounts
        ]

        return account_responses

    async def get_customer_account_details(self, user_id: int, account_type_id: int) -> dict:
        logger.info(f"Getting account details for UserId: {user_id} and AccountTypeId: {account_type_id}")

        account_response = await self.account_service.get_customer_account_details(user_id, account_type_id)

        if account_response is None:
            logger.error("Account not found.")
            return None

        logger.info("Mapping retrieved account details to account response")
        account_data_dict = _convert_account_response_to_dict(account_response)

        return account_data_dict
