import logging
from aiomysql import DictCursor
from Dtos.Request.UserRequest import UserRequest
from SqlQueries.user_sql_queries import USER_QUERIES
from Utility.Security import hash_password


class UserService:
    def __init__(self, database_connection):
        self.database_connection = database_connection

    async def create_user(self, user_request: UserRequest):
        connection = await self.database_connection.get_connection()
        if not connection:
            logging.error("Database connection could not be established")
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                # Check if the user already exists
                await cursor.execute(USER_QUERIES["CHECK_EXISTING_USER"], (user_request.email,))
                existing_user = await cursor.fetchone()

                if existing_user:
                    logging.warning(f"User with email {user_request.email} already exists")
                    return None  # Return None if user exists

                # Hash the password before inserting it
                hashed_password = hash_password(user_request.password)

                # Insert new user
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
            logging.error(f"Error creating user: {e}", exc_info=True)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)
