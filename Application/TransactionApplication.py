from Dtos.Response.AccountResponse import AccountResponse
from Repository.transaction_repository import TransactionRepository
from Service.TransactionService import TransactionService
from logger import logger


class TransactionApplication:
    def __init__(self, transaction_repo: TransactionRepository, transaction_service: TransactionService):
        self.transaction_repo = transaction_repo
        self.transaction_service = transaction_service

    async def get_customer_account_details(self, customer_id: int, account_type_id: int) -> dict:
        try:
            print("Transaction application")
            response = await self.transaction_service.get_customer_account_details(customer_id, account_type_id)
            if response is None:
                logger.error("Failed to get customer accounts.")
                return None

            logger.info("Mapping retrieved account details to account response")
            account_data_dict = _convert_account_response_to_dict(response)

            return account_data_dict
        except Exception as e:
            print(f"Error processing customer account: {e}")
            return None


def _convert_account_response_to_dict(account_response: AccountResponse) -> dict:
    accounts_list = []
    for account in account_response.accounts:
        account_dict = {
            "account_number": account.account_number,
            "balance": account.balance,
            "account_type": account.account_type if account.account_type else None,
            "account_type_id": account.account_type if account.account_type else None,
        }
        accounts_list.append(account_dict)

    return {
        "user_id": account_response.user_id,
        "customer_id": account_response.customer_id,
        "last_name": account_response.last_name,
        "first_name": account_response.first_name,
        "email": account_response.email,
        "accounts": accounts_list,
    }
