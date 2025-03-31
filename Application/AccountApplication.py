from database_connection import DatabaseConnection
from logger import logger
from typing import Any, Optional, List
from Service.AccountService import AccountService


class AccountApplication:
    def __init__(self):
        self.database_connection = DatabaseConnection()
        self.account_service = AccountService(self.database_connection)

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
