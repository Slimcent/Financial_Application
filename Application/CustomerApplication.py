from typing import Optional, List

from Dtos.Request.CustomerRequest import CustomerRequest
from Dtos.Response.UserResponse import UserResponse
from Service.CustomerService import CustomerService
from Service.UserService import UserService
from database_connection import DatabaseConnection
from logger import logger


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

    async def get_all_customers(self) -> Optional[List[UserResponse]]:
        logger.info("Fetching all customers...")

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
                "account_type": customer.account_type,
                "balance": customer.balance,
                "active": customer.active,
                "created_at": customer.created_at.strftime("%Y-%m-%d %H:%M:%S") if customer.created_at else None
            }
            for customer in customers
        ]

        return customer_responses
