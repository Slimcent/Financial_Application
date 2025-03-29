from Dtos.Request.CustomerRequest import CustomerRequest
from Dtos.Request.UserRequest import UserRequest
from Infrastructure.AppConstants import AppConstants
from SqlQueries.customer_sql_queries import CUSTOMER_QUERIES
from logger import logger


class CustomerService:
    def __init__(self, database_connection, user_service):
        self.database_connection = database_connection
        self.user_service = user_service
        self.constants = AppConstants

    async def create_customer(self, customer_request: CustomerRequest):
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor() as cursor:
                # Begin transaction
                await connection.begin()

                user_request = UserRequest(
                    last_name=customer_request.last_name,
                    first_name=customer_request.first_name,
                    email=customer_request.email,
                    password="new_customer",
                    role_id=self.constants.CustomerRoleId,
                )

                logger.info("Creating customer as user first")
                user_id = await self.user_service.create_user(user_request)

                if not user_id:
                    raise Exception("Failed to create user for customer")

                logger.info(f"Created user with Id: {user_id}")

                await cursor.execute(CUSTOMER_QUERIES["CREATE_CUSTOMER"],
                                     (user_id, customer_request.account_Type_id, 0.0))

                # Commit transaction
                await connection.commit()

                logger.info(f"Customer created successfully for User Id {user_id}")
                return user_id

        except Exception as e:
            logger.error(f"Error creating customer: {e}", exc_info=True)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)
