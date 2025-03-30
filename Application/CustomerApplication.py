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

        await self.delete_customer(15)

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
