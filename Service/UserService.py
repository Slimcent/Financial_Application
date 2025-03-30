from logger import logger
from aiomysql import DictCursor
from Utility.Security import hash_password
from Dtos.Request.UserRequest import UserRequest
from SqlQueries.user_sql_queries import USER_QUERIES
from Dtos.Request.UpdateUserRequest import UpdateUserRequest


class UserService:
    def __init__(self, database_connection):
        self.database_connection = database_connection

    async def create_user(self, user_request: UserRequest):
        connection = await self.database_connection.get_connection()
        if not connection:
            logger.error("Database connection could not be established")
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                # Check if the user already exists
                await cursor.execute(USER_QUERIES["CHECK_EXISTING_USER"], (user_request.email,))
                existing_user = await cursor.fetchone()

                if existing_user:
                    logger.warning(f"User with email {user_request.email} already exists")
                    return None

                # Hash the password before inserting it
                hashed_password = hash_password(user_request.password)

                # Insert new user
                logger.info("Inserting into user table")
                await cursor.execute(USER_QUERIES["INSERT_NEW_USER"], (
                    user_request.last_name,
                    user_request.first_name,
                    user_request.email,
                    user_request.role_id,
                    hashed_password
                ))
                await connection.commit()

                return cursor.lastrowid

        except Exception as e:
            logger.error(f"Error creating user: {e}", exc_info=True)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def toggle_user_active_status(self, user_id: int):
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                await cursor.execute(USER_QUERIES["GET_USER_ACTIVE_STATUS"], (user_id,))
                user = await cursor.fetchone()

                if not user:
                    logger.warning(f"User with ID {user_id} not found.")
                    return None

                logger.info(f"Found {user['LastName']} {user['FirstName']}")
                active_status = user["Active"] if "Active" in user else None

                new_status = 0 if active_status == 1 else 1

                # Update the active status
                logger.info(f"Updating the status of {user['LastName']} {user['FirstName']} "
                            f"with status {user['Active'] == 1}")
                await cursor.execute(USER_QUERIES["TOGGLE_USER_ACTIVE_STATUS"], (new_status, user_id))
                await connection.commit()

                logger.info(f"User ID {user_id} active status changed to {bool(new_status)}.")
                return bool(new_status)

        except Exception as e:
            logger.error(f"Error toggling active status for user {user_id}: {e}", exc_info=True)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def update_user(self, user_id: int, update_request: UpdateUserRequest):
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor() as cursor:
                # Start a transaction
                await connection.begin()

                # Check if the user exists
                await cursor.execute(USER_QUERIES["GET_USER_BY_ID"], (user_id,))
                user = await cursor.fetchone()

                if not user:
                    logger.warning(f"User with ID {user_id} not found.")
                    return None

                await cursor.execute(USER_QUERIES["UPDATE_USER"], (update_request.last_name, update_request.first_name,
                                                                   update_request.email, user_id))

                await connection.commit()

                return True

        except Exception as e:
            logger.error(f"Error updating user with ID {user_id}: {e}", exc_info=True)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def delete_user(self, user_id: int):
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                logger.info(f"Checking if the user with user id {user_id} exists")
                await cursor.execute(USER_QUERIES["GET_USER_BY_ID"], (user_id,))
                user = await cursor.fetchone()

                if not user:
                    logger.warning(f"User with Id {user_id} not found.")
                    return None

                logger.info(f"Deleting user {user['FirstName']} {user['LastName']} (Id: {user_id})")

                await cursor.execute(USER_QUERIES["DELETE_USER"], (user_id,))

                logger.info(f"User with Id {user_id} successfully deleted.")
                return True

        except Exception as e:
            logger.error(f"Error deleting user with ID {user_id}: {e}", exc_info=True)
            return None

        finally:
            await self.database_connection.release_connection(connection)
