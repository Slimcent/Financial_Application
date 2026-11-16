import uuid
from Data.Interfaces.i_unit_of_work import UnitOfWorkFactory
from Infrastructure.Logging.logger import logger
from typing import Any
from Models.Dtos.Response.UserResponse import UserResponse
from Models.Dtos.Request.CustomerRequest import CustomerRequest
from Models.Dtos.Request.CustomerUpdateRequest import CustomerUpdateRequest
from Services.Exceptions.domain_exceptions import ServiceError
from Services.Interfaces.i_customer_service import ICustomerService

# Placeholder for the demo calls below: replace with a real Users.Id (GUID) from your database.
SAMPLE_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


class CustomerApplication:
    def __init__(self, unit_of_work_factory: UnitOfWorkFactory, customer_service: ICustomerService):
        self.unit_of_work_factory = unit_of_work_factory
        self.customer_service = customer_service

    async def run_application(self):
        # await self.delete_customer(SAMPLE_USER_ID)
        await self.get_customer_details(SAMPLE_USER_ID)
        # await self.add_or_update_customer_account_type(SAMPLE_USER_ID, 1)
        # await self.close_customer_account(SAMPLE_USER_ID, "2600000000")
        # await self.deactivate_customer_account(SAMPLE_USER_ID)
        # customers = await self.get_all_customers()
        # if customers:
        #     for customer in customers:
        #         print(customer)

    async def create_customer(self, customer_request: CustomerRequest):
        logger.info(f"Starting to create customer {customer_request.email}")
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                customer = await self.customer_service.create_customer(unit_of_work, customer_request)
        except ServiceError as error:
            logger.warning(f"Failed to create customer: {error.message}")
            return None

        logger.info(f"Customer created successfully with User Id: {customer.user_id}")
        return customer

    async def update_customer(self, user_id: uuid.UUID, customer_request: CustomerUpdateRequest):
        logger.info(f"Starting the update of customer with the user id {user_id}")
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                result = await self.customer_service.update_customer(unit_of_work, user_id, customer_request)
        except ServiceError as error:
            logger.warning(f"Failed to update customer with User ID {user_id}: {error.message}")
            return None

        logger.info(f"Customer with User ID {user_id} updated successfully.")
        return result

    async def delete_customer(self, user_id: uuid.UUID):
        logger.info(f"Starting to delete customer with user id {user_id}")
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                await self.customer_service.delete_customer(unit_of_work, user_id)
        except ServiceError as error:
            logger.warning(f"Failed to delete customer {user_id}: {error.message}")
            return False

        logger.info(f"Customer with user id {user_id} deleted successfully.")
        return True

    async def get_all_customers(self) -> list[dict[str, Any]]:
        logger.info("Getting all customers...")

        async with self.unit_of_work_factory() as unit_of_work:
            customers = await self.customer_service.get_all_customers(unit_of_work)

        if not customers:
            logger.info("No customers found.")
            return []

        customer_responses = [
            {
                "user_id": customer.user_id,
                "customer_id": customer.customer_id,
                "last_name": customer.last_name,
                "first_name": customer.first_name,
                "email": customer.email,
                "address": customer.address,
                "role_id": customer.role_id,
                "role_name": customer.role_name,
                "accounts": [vars(account) for account in customer.accounts],
                "active": customer.active,
                "created_at": customer.created_at.strftime("%Y-%m-%d %H:%M:%S") if customer.created_at else None
            }
            for customer in customers
        ]

        return customer_responses

    async def get_customer_details(self, user_id: uuid.UUID) -> UserResponse | None:
        logger.info(f"getting customer details with the user id {user_id}")
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                customer = await self.customer_service.get_customer_by_id(unit_of_work, user_id)
        except ServiceError as error:
            logger.warning(error.message)
            return None

        account_descriptions = [
            f"{account.account_type} (Id: {account.account_type_id}, Number: {account.account_number}, "
            f"Balance: {account.balance})"
            for account in customer.accounts
        ]

        print(
            f"Retrieved Customer Details:\n"
            f"Name: {customer.first_name} {customer.last_name}\n"
            f"User Id: {customer.user_id}\n"
            f"Customer Id: {customer.customer_id}\n"
            f"Email: {customer.email}\n"
            f"Address: {customer.address}\n"
            f"Role: {customer.role_name} (Role Id: {customer.role_id})\n"
            f"Active: {customer.active}\n"
            f"Created At: {customer.created_at}\n"
            f"Accounts: {', '.join(account_descriptions)}"
        )

        return customer

    async def close_customer_account(self, user_id: uuid.UUID, account_number: str):
        logger.info(f"Starting to close account {account_number} of customer {user_id}")
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                await self.customer_service.close_account(unit_of_work, user_id, account_number)
        except ServiceError as error:
            logger.warning(f"Failed to close account {account_number} of customer {user_id}: {error.message}")
            return False

        logger.info(f"Account {account_number} of customer {user_id} closed successfully.")
        return True

    async def deactivate_customer_account(self, user_id: uuid.UUID) -> UserResponse | None:
        logger.info(f"Starting to deactivate customer {user_id} and the customer's accounts")
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                customer = await self.customer_service.deactivate_customer_account(unit_of_work, user_id)
        except ServiceError as error:
            logger.warning(f"Failed to deactivate customer {user_id}: {error.message}")
            return None

        logger.info(f"Customer {user_id} and the customer's accounts deactivated (active: {customer.active}).")
        return customer

    async def add_or_update_customer_account_type(self, user_id: uuid.UUID, account_type_id: int):
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                account = await self.customer_service.open_account(unit_of_work, user_id, account_type_id)
        except ServiceError as error:
            logger.error(f"Failed to add account type {account_type_id} for user {user_id}: {error.message}")
            print(f"Failed to add account type {account_type_id} for user {user_id}.")
            return None

        logger.info(f"Successfully added account type {account_type_id} for user {user_id}.")
        print(f"Account {account.account_number} ({account.account_type}) successfully opened for user {user_id}.")
        return account
