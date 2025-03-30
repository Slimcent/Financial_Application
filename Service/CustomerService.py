from logger import logger
from datetime import datetime
from aiomysql import DictCursor
from typing import List, Optional
from Dtos.Request.UserRequest import UserRequest
from Dtos.Response.UserResponse import UserResponse
from Infrastructure.AppConstants import AppConstants
from Dtos.Request.CustomerRequest import CustomerRequest
from Dtos.Request.UpdateUserRequest import UpdateUserRequest
from SqlQueries.customer_sql_queries import CUSTOMER_QUERIES


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

    async def update_customer(self, user_id: int, customer_request: CustomerRequest):
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                await cursor.execute(CUSTOMER_QUERIES["GET_CUSTOMER_BY_USER_ID"], (user_id,))
                customer = await cursor.fetchone()

                if not customer:
                    logger.warning(f"Customer with UserId {user_id} not found.")
                    return None

                logger.info(f"Updating user details for customer with UserId {user_id}.")

                user_update_request = UpdateUserRequest(
                    last_name=customer_request.last_name,
                    first_name=customer_request.first_name,
                    email=customer_request.email,
                )

                await self.user_service.update_user(user_id, user_update_request)

                logger.info(f"Successfully updated customer {user_id}.")
                return True

        except Exception as e:
            logger.error(f"Error updating customer {user_id}: {e}", exc_info=True)
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def delete_customer(self, user_id: int):
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:

                await cursor.execute(CUSTOMER_QUERIES["GET_CUSTOMER_BY_USER_ID"], (user_id,))
                customer = await cursor.fetchone()

                if not customer:
                    logger.warning(f"Customer with UserId {user_id} not found.")
                    return None

                await cursor.execute(CUSTOMER_QUERIES["DELETE_CUSTOMER"], (user_id,))
                logger.info(f"Successfully deleted customer with UserId {user_id}.")

                await self.user_service.delete_user(user_id)

                return True

        except Exception as e:
            logger.error(f"Error deleting customer with UserId {user_id}: {e}", exc_info=True)
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def get_all_customers(self) -> Optional[List[UserResponse]]:
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                await cursor.execute(CUSTOMER_QUERIES["GET_ALL_CUSTOMERS"])
                customers = await cursor.fetchall()

                if not customers:
                    logger.info("No customers found.")
                    return []

                customer_list = [
                    UserResponse(
                        user_id=customer["UserId"],
                        staff_id=None,
                        first_name=customer["FirstName"],
                        last_name=customer["LastName"],
                        email=customer["Email"],
                        position=None,
                        role_id=customer["RoleId"],
                        role_name=customer["RoleName"],
                        account_type=customer["AccountTypeId"],
                        balance=str(customer["Balance"]),
                        active=customer["Active"] == 1,
                        created_at=customer["CreatedAt"] if isinstance(customer["CreatedAt"], datetime) else None,
                    )
                    for customer in customers
                ]

                logger.info(f"Retrieved {len(customer_list)} customers.")
                return customer_list

        except Exception as e:
            logger.error(f"Error retrieving customers: {e}", exc_info=True)
            return None

        finally:
            await self.database_connection.release_connection(connection)
