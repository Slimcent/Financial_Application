from logger import logger
from typing import Optional, List
from Dtos.Response.AccountResponse import AccountResponse
from Repository.AccountRepository import AccountRepository


class AccountService:
    def __init__(self, account_repository: AccountRepository):
        self.account_repository = account_repository

    async def get_all_customer_accounts(self) -> Optional[List[AccountResponse]]:
        data = await self.account_repository.get_all_customer_accounts()

        if data is None:
            logger.error("Failed to fetch customer accounts from repository.")
            return None

        if not data:
            logger.info("No customer accounts found.")
            return []

        customer_dict = {}

        for row in data:
            user_id = row["UserId"]

            if user_id not in customer_dict:
                customer_dict[user_id] = AccountResponse(
                    user_id=user_id,
                    first_name=row["FirstName"],
                    last_name=row["LastName"],
                    email=row["Email"],
                    account_types=[]
                )

            customer_dict[user_id].account_types.append({
                "account_type_id": row["AccountTypeId"],
                "account_type_name": row["AccountType"],
                "account_number": row["AccountNumber"],
                "balance": str(row["Balance"] or 0)
            })

        logger.info(f"Got {len(customer_dict)} customers with accounts.")
        return list(customer_dict.values())

    async def get_customer_account_details(self, user_id: int, account_type_id: int) -> AccountResponse | None:
        account_data = await self.account_repository.get_customer_account_details(user_id, account_type_id)

        if account_data is None:
            logger.error("Account not found.")
            return None

        logger.info("Account details retrieved in the service method")
        account_types = [
            {
                "account_type_id": account_data["AccountTypeId"],
                "account_type_name": account_data["AccountType"],
                "account_number": account_data["AccountNumber"],
                "balance": account_data["Balance"] or 0.0
            }
        ]

        account_response = AccountResponse(
            user_id=account_data["UserId"],
            last_name=account_data["LastName"],
            first_name=account_data["FirstName"],
            email=account_data["Email"],
            account_type_id=account_data["AccountTypeId"],
            account_type=account_data["AccountType"],
            account_number=account_data["AccountNumber"],
            balance=account_data["Balance"] or 0.0,
            account_types=account_types
        )

        return account_response

