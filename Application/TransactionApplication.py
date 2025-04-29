from typing import Optional, Dict, Any

from Dtos.Request.transaction_request import UserTransactionsRequest, TransactionsRequest
from Dtos.Response.AccountResponse import AccountResponse
from Dtos.Response.AccountsResponse import AccountsResponse
from Dtos.Response.paged_response import PagedResponse
from Dtos.Response.transaction_response import TransactionsResponse
from Repository.transaction_repository import TransactionRepository
from Service.transaction_service import TransactionService
from logger import logger


class TransactionApplication:
    def __init__(self, transaction_repo: TransactionRepository, transaction_service: TransactionService):
        self.transaction_repo = transaction_repo
        self.transaction_service = transaction_service

    async def get_customer_account(self, user_id: int, account_type_id: int) -> dict:
        try:
            print("Transaction application")
            response = await self.transaction_service.get_customer_account(user_id, account_type_id)
            if response is None:
                logger.error("Failed to get customer accounts.")
                return None

            logger.info("Mapping retrieved account details to account response")
            account_data_dict = _convert_account_response_to_dict(response)

            return account_data_dict
        except Exception as e:
            print(f"Error processing customer account: {e}")
            return None

    async def get_customer_accounts_with_user_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        customer = await self.transaction_service.get_customer_accounts_with_user_id(user_id)

        if not customer:
            return None

        logger.info("Mapping retrieved account details to account response")
        account_data_dict = _convert_account_response_to_dict(customer)

        return account_data_dict

    async def get_account_details_by_account_number(self, account_number: str) -> Optional[AccountsResponse]:
        return await self.transaction_service.get_account_details_by_account_number(account_number)

    async def get_account_balance_by_account_number(self, account_number: str) -> Optional[float]:
        account = await self.transaction_service.get_account_details_by_account_number(account_number)
        if account:
            return account.balance
        return None

    async def fund_account(self, account_number: str, amount: float, description: Optional[str] = None) \
            -> AccountsResponse:
        return await self.transaction_service.fund_account(account_number, amount, description)

    async def get_user_transactions(self, user_id: int) -> Optional[AccountResponse]:
        return await self.transaction_service.get_user_transactions(user_id)

    async def filter_user_transactions(self, request: UserTransactionsRequest) -> Optional[AccountResponse]:
        return await self.transaction_service.filter_user_transactions(request)

    async def get_all_transactions_paginated(self, request: TransactionsRequest) -> PagedResponse[TransactionsResponse]:
        return await self.transaction_service.get_all_transactions_paginated(request)


def _convert_account_response_to_dict(account_response: AccountResponse) -> dict:
    accounts_list = []
    for account in account_response.accounts:
        account_dict = {
            "account_id": account.account_id,
            "account_number": account.account_number,
            "balance": account.balance,
            "account_type_id": account.account_type_id if account.account_type else None,
            "account_type": account.account_type if account.account_type else None,
        }
        accounts_list.append(account_dict)

    return {
        "user_id": account_response.user_id,
        "customer_id": account_response.customer_id,
        "last_name": account_response.last_name,
        "first_name": account_response.first_name,
        "email": account_response.email,
        "accounts": accounts_list,
        "total_balance": account_response.total_balance
    }
