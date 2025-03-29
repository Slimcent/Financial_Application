from Dtos.Request.CustomerRequest import CustomerRequest
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
        await self.create_customer(customer_request=CustomerRequest(
            last_name="Mendy",
            first_name="Mal",
            email="mendy@yopmail.com",
            account_Type_Id=1
        ))

    async def create_customer(self, customer_request: CustomerRequest):
        logger.info(f"Starting to create customer {customer_request.email}")
        result = await self.customer_service.create_customer(customer_request)

        if result:
            logger.info(f"Customer created successfully with User Id: {result}")
        else:
            logger.warning("Failed to create customer.")
