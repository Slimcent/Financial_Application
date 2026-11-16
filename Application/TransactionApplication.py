import uuid
from decimal import Decimal
from typing import Optional, Dict, Any, List

from Data.Interfaces.i_unit_of_work import UnitOfWorkFactory
from Models.Dtos.Request.fund_account_request import FundAccountRequest
from Models.Dtos.Request.transaction_request import UserTransactionsRequest, TransactionsRequest, FundsTransferRequest
from Models.Dtos.Response.AccountResponse import AccountResponse
from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Response.paged_response import PagedResponse
from Models.Dtos.Response.transaction_response import TransactionsResponse
from Services.Exceptions.domain_exceptions import ServiceError
from Services.Interfaces.i_account_service import IAccountService
from Services.Interfaces.i_transaction_service import ITransactionService
from Infrastructure.Logging.logger import logger


class TransactionApplication:
    def __init__(self, unit_of_work_factory: UnitOfWorkFactory, account_service: IAccountService,
                 transaction_service: ITransactionService):
        self.unit_of_work_factory = unit_of_work_factory
        self.account_service = account_service
        self.transaction_service = transaction_service

    async def get_customer_account(self, user_id: uuid.UUID, account_type_id: int) -> Optional[Dict[str, Any]]:
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                response = await self.account_service.get_customer_account_details(unit_of_work, user_id,
                                                                                    account_type_id)
        except ServiceError as error:
            logger.error(f"Failed to get the customer account: {error.message}")
            return None

        logger.info("Mapping retrieved account details to account response")
        return _convert_account_response_to_dict(response)

    async def get_customer_accounts_with_user_id(self, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                customer = await self.account_service.get_customer_accounts_with_user_id(unit_of_work, user_id)
        except ServiceError as error:
            logger.error(f"Failed to get the customer accounts: {error.message}")
            return None

        logger.info("Mapping retrieved account details to account response")
        return _convert_account_response_to_dict(customer)

    async def get_account_details_by_account_number(self, account_number: str) -> Optional[AccountsResponse]:
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                return await self.account_service.get_account_details_by_account_number(unit_of_work,
                                                                                        account_number)
        except ServiceError as error:
            logger.warning(error.message)
            return None

    async def get_account_balance_by_account_number(self, account_number: str) -> Optional[Decimal]:
        account = await self.get_account_details_by_account_number(account_number)
        if account:
            return account.balance
        return None

    async def fund_account(self, request: FundAccountRequest) -> Optional[AccountsResponse]:
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                return await self.transaction_service.fund_account(unit_of_work, request)
        except ServiceError as error:
            logger.error(f"Account funding failed: {error.message}")
            return None

    async def get_user_transactions(self, user_id: uuid.UUID) -> Optional[AccountResponse]:
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                return await self.transaction_service.get_user_transactions(unit_of_work, user_id)
        except ServiceError as error:
            logger.warning(error.message)
            return None

    async def filter_user_transactions(self, request: UserTransactionsRequest) -> Optional[AccountResponse]:
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                return await self.transaction_service.filter_user_transactions(unit_of_work, request)
        except ServiceError as error:
            logger.warning(error.message)
            return None

    async def get_all_transactions_paginated(self, request: TransactionsRequest) -> PagedResponse[TransactionsResponse]:
        async with self.unit_of_work_factory() as unit_of_work:
            return await self.transaction_service.get_all_transactions_paginated(unit_of_work, request)

    async def get_all_transactions_non_paginated(self, request: TransactionsRequest) -> List[TransactionsResponse]:
        async with self.unit_of_work_factory() as unit_of_work:
            return await self.transaction_service.get_all_transactions_non_paginated(unit_of_work, request)

    async def transfer_funds(self, request: FundsTransferRequest) -> Optional[AccountsResponse]:
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                return await self.transaction_service.transfer_funds(unit_of_work, request)
        except ServiceError as error:
            logger.error(f"Transfer failed: {error.message}")
            return None


def _convert_account_response_to_dict(account_response: AccountResponse) -> dict:
    accounts_list = []
    for account in account_response.accounts:
        account_dict = {
            "account_id": account.account_id,
            "account_number": account.account_number,
            "balance": account.balance,
            "account_type_id": account.account_type_id,
            "account_type": account.account_type,
        }
        accounts_list.append(account_dict)

    return {
        "user_id": account_response.user_id,
        "customer_id": account_response.customer_id,
        "last_name": account_response.last_name,
        "first_name": account_response.first_name,
        "email": account_response.email,
        "address": account_response.address,
        "accounts": accounts_list,
        "total_balance": account_response.total_balance
    }
