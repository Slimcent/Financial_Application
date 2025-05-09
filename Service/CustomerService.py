from logger import logger
from datetime import datetime
from aiomysql import DictCursor
from typing import List, Optional
from collections import defaultdict
from Dtos.Request.UserRequest import UserRequest
from Dtos.Response.UserResponse import UserResponse
from Infrastructure.AppConstants import AppConstants
from Dtos.Request.CustomerRequest import CustomerRequest
from Utility.AccountNumber import generate_account_number
from SqlQueries.account_sql_queries import ACCOUNT_QUERIES
from Dtos.Request.UpdateUserRequest import UpdateUserRequest
from SqlQueries.customer_sql_queries import CUSTOMER_QUERIES
from Dtos.Response.AccountsResponse import AccountsResponse


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
                await connection.begin()

                account_number = await generate_account_number(customer_request.account_type_id)

                # Create user first
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

                # Insert into Customers table
                await cursor.execute(CUSTOMER_QUERIES["CREATE_CUSTOMER"],
                                     (user_id, customer_request.address))

                customer_id = cursor.lastrowid

                if not customer_id:
                    raise Exception("Failed to create customer record")

                logger.info(f"Created customer with Id: {customer_id}")

                # Insert into Accounts table
                await cursor.execute(ACCOUNT_QUERIES["CREATE_ACCOUNT"],
                                     (user_id, customer_request.account_type_id, account_number, 0.0))

                await connection.commit()

                logger.info(f"Customer and account created successfully for User Id {user_id}")
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
                # Get the existing customer details
                await cursor.execute(CUSTOMER_QUERIES["GET_Single_CUSTOMER"], (user_id,))
                customer = await cursor.fetchone()

                if not customer:
                    logger.warning(f"Customer with UserId {user_id} not found.")
                    return None

                logger.info(f"Updating user details for customer with UserId {user_id}.")

                # Update user details
                user_update_request = UpdateUserRequest(
                    last_name=customer_request.last_name,
                    first_name=customer_request.first_name,
                    email=customer_request.email,
                )
                await self.user_service.update_user(user_id, user_update_request)

                # Update customer address
                logger.info(f"Updating address for customer with UserId {user_id}.")
                await cursor.execute(CUSTOMER_QUERIES["UPDATE_CUSTOMER"], (customer_request.address, user_id))

                # Commit the transaction
                await connection.commit()
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

                await cursor.execute(CUSTOMER_QUERIES["GET_Single_CUSTOMER"], (user_id,))
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

                # Dictionary to group account types by UserId
                customer_dict = defaultdict(lambda: {
                    "user_id": None,
                    "customer_id": None,
                    "staff_id": None,
                    "first_name": None,
                    "last_name": None,
                    "email": None,
                    "address": None,
                    "position": None,
                    "role_id": None,
                    "role_name": None,
                    "balance": None,
                    "active": None,
                    "created_at": None,
                    "accounts": []
                })

                for customer in customers:
                    user_id = customer["UserId"]
                    if customer_dict[user_id]["user_id"] is None:
                        customer_dict[user_id].update({
                            "user_id": user_id,
                            "customer_id": customer["CustomerId"],
                            "first_name": customer["FirstName"],
                            "last_name": customer["LastName"],
                            "email": customer["Email"],
                            "address": customer["Address"],
                            "role_id": customer["RoleId"],
                            "role_name": customer["RoleName"],
                            "balance": str(customer["Balance"]),
                            "active": customer["Active"] == 1,
                            "created_at": customer["CreatedAt"] if isinstance(customer["CreatedAt"], datetime) else None
                        })

                    # Append account type to the list
                    if customer["AccountTypeId"]:
                        customer_dict[user_id]["accounts"].append({
                            "account_type_id": customer["AccountTypeId"],
                            "account_type": customer["AccountType"]
                        })

                # Convert dictionary values to UserResponse objects
                customer_list = [
                    UserResponse(
                        user_id=data["user_id"],
                        customer_id=data["customer_id"],
                        first_name=data["first_name"],
                        last_name=data["last_name"],
                        email=data["email"],
                        address=data["address"],
                        position=data["position"],
                        role_id=data["role_id"],
                        role_name=data["role_name"],
                        active=data["active"],
                        created_at=data["created_at"],
                        accounts=data["accounts"]
                    )
                    for data in customer_dict.values()
                ]

                logger.info(f"Retrieved {len(customer_list)} customers.")
                return customer_list

        except Exception as e:
            logger.error(f"Error retrieving customers: {e}", exc_info=True)
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def get_customer_by_id(self, user_id: int) -> UserResponse | None:
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                await cursor.execute(CUSTOMER_QUERIES["GET_CUSTOMER_BY_USER_ID"], (user_id,))
                customer_rows = await cursor.fetchall()

                if not customer_rows:
                    logger.warning(f"Customer with User Id {user_id} not found.")
                    return None

                accounts = []

                for row in customer_rows:
                    if row["AccountId"] is not None:
                        accounts.append(AccountsResponse(
                            account_id=row["AccountId"],
                            account_number=row["AccountNumber"],
                            balance=row["Balance"],
                            account_type_id=row["AccountTypeId"],
                            account_type=row["AccountType"]
                        ))

                first_row = customer_rows[0]
                user_response = UserResponse(
                    user_id=first_row["UserId"],
                    customer_id=first_row["CustomerId"],
                    last_name=first_row["LastName"],
                    first_name=first_row["FirstName"],
                    email=first_row["Email"],
                    address=first_row["Address"],
                    role_id=first_row["RoleId"],
                    role_name=first_row["RoleName"],
                    accounts=accounts,
                    active=first_row["Active"] == 1,
                    created_at=first_row["CreatedAt"] if first_row["CreatedAt"] else None,
                )

                return user_response

        except Exception as e:
            logger.error(f"Error getting customer with Id {user_id}: {e}", exc_info=True)
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def add_or_update_account_type(self, user_id: int, account_type_id: int) -> bool:
        connection = await self.database_connection.get_connection()
        if not connection:
            return False

        try:
            async with connection.cursor(DictCursor) as cursor:
                logger.info(f"Getting all existing account types for user {user_id}...")
                await cursor.execute(CUSTOMER_QUERIES["GET_CUSTOMER_ACCOUNT_TYPES"], (user_id,))
                existing_account_types = {row["AccountTypeId"] for row in await cursor.fetchall()}

                if not existing_account_types:
                    logger.warning(f"Customer with user Id {user_id} does not exist.")
                    return False

                account_number = await generate_account_number(account_type_id=account_type_id)

                if account_type_id in existing_account_types:
                    logger.info(f"Account type {account_type_id} already exists for customer {user_id}. "
                                f"No action needed.")
                    return True

                # If account type does not exist, insert it
                logger.info(f"Adding new account type {account_type_id} for user {user_id}...")
                await cursor.execute(CUSTOMER_QUERIES["CREATE_ACCOUNT"], (user_id, account_type_id,
                                                                          account_number, 0.0))
                await connection.commit()

                logger.info(f"Account type {account_type_id} successfully added for user {user_id}.")
                return True

        except Exception as e:
            logger.error(f"Error adding account type for user {user_id}: {e}", exc_info=True)
            await connection.rollback()
            return False

        finally:
            await self.database_connection.release_connection(connection)
