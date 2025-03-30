from logger import logger
from Service.UserService import UserService
from typing import Optional, List, Any, Dict
from database_connection import DatabaseConnection
from Service.CustomerService import CustomerService
from Dtos.Response.UserResponse import UserResponse
from Dtos.Request.CustomerRequest import CustomerRequest


class CustomerApplication:
    def __init__(self):
        self.database_connection = DatabaseConnection()
        self.user_service = UserService(self.database_connection)
        self.customer_service = CustomerService(self.database_connection, self.user_service)

    async def run_application(self):
        # await self.create_customer(customer_request=CustomerRequest(
        #     last_name="Mendy",
        #     first_name="Mal",
        #     email="mendy@yopmail.com",
        #     account_Type_Id=1
        # ))

        # await self.update_customer(9, customer_request=CustomerRequest(
        #     last_name="Ebus",
        #     first_name="Rhema",
        #     email="ebus@yopmail.com",
        #     account_Type_Id=None
        # ))

        # await self.delete_customer(15)
        # await self.get_customer_details(8)
        # await self.add_or_update_customer_account_type(7, 2)
        customers = await self.get_all_customers()
        if customers:
            for customer in customers:
                print(customer)

    async def create_customer(self, customer_request: CustomerRequest):
        logger.info(f"Starting to create customer {customer_request.email}")
        result = await self.customer_service.create_customer(customer_request)

        if result:
            logger.info(f"Customer created successfully with User Id: {result}")
        else:
            logger.warning("Failed to create customer.")

    async def update_customer(self, user_id: int, customer_request: CustomerRequest):
        logger.info(f"Starting the update of customer with the user id {user_id}")
        result = await self.customer_service.update_customer(user_id, customer_request)

        if result:
            logger.info(f"Staff with User ID {user_id} updated successfully.")
        else:
            logger.warning(f"Failed to update staff with User ID {user_id}.")

        return result

    async def delete_customer(self, user_id: int):
        logger.info(f"Starting to delete customer with user id {user_id}")
        result = await self.customer_service.delete_customer(user_id)
        if result:
            logger.info(f"Customer with user id {user_id} deleted successfully.")
        else:
            logger.warning(f"Failed to delete customer {user_id}.")

    async def get_all_customers(self) -> None | list[Any] | list[dict[str, str | None | int | bool | Any]]:
        logger.info("Getting all customers...")

        customers = await self.customer_service.get_all_customers()

        if customers is None:
            logger.error("Failed to retrieve customers.")
            return None

        if not customers:
            logger.info("No customers found.")
            return []

        customer_responses = [
            {
                "user_id": customer.user_id,
                "last_name": customer.last_name,
                "first_name": customer.first_name,
                "email": customer.email,
                "role_id": customer.role_id,
                "role_name": customer.role_name,
                "account_types": customer.account_types,
                "balance": customer.balance,
                "active": customer.active,
                "created_at": customer.created_at.strftime("%Y-%m-%d %H:%M:%S") if customer.created_at else None
            }
            for customer in customers
        ]

        return customer_responses

    async def get_customer_details(self, user_id: int) -> UserResponse | None:
        logger.info(f"getting customer details with the user id {user_id}")
        customer = await self.customer_service.get_customer_by_id(user_id)

        if not customer:
            logger.warning(f"Customer with User ID {user_id} not found.")
            return None

        account_types = [
            f"{account['account_type']} (Id: {account['account_type_id']})"
            for account in customer.account_types
        ]

        print(
            f"Retrieved Customer Details:\n"
            f"Name: {customer.first_name} {customer.last_name}\n"
            f"User Id: {customer.user_id}\n"
            f"Email: {customer.email}\n"
            f"Role: {customer.role_name} (Role Id: {customer.role_id})\n"
            f"Active: {customer.active}\n"
            f"Created At: {customer.created_at}\n"
            f"Account Types: {', '.join(account_types)}"
        )

        return customer

    async def add_or_update_customer_account_type(self, user_id: int, account_type_id: int):
        success = await self.customer_service.add_or_update_account_type(user_id, account_type_id)

        if success:
            logger.info(f"Successfully added/updated account type {account_type_id} for user {user_id}.")
            print(f"Account type {account_type_id} successfully added/updated for user {user_id}.")
        else:
            logger.error(f"Failed to add/update account type {account_type_id} for user {user_id}.")
            print(f"Failed to update account type for user {user_id}.")
