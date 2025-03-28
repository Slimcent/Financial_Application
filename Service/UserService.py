from aiomysql import DictCursor
from Dtos.Request.UserRequest import UserRequest


class UserService:
    def __init__(self, database_connection):
        self.database_connection = database_connection

    async def create_user(self, user_request: UserRequest):
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                # Check if the user already exists
                check_query = "SELECT Id FROM Users WHERE Email = %s"
                await cursor.execute(check_query, (user_request.email,))
                existing_user = await cursor.fetchone()

                if existing_user:
                    print("User with this email already exists")
                    return None  # Return None if user exists

                # Insert new user
                insert_query = "INSERT INTO Users (LastName, FirstName, Email, RoleId, Password) VALUES (%s, %s, %s, " \
                               "%s, %s) "
                await cursor.execute(insert_query, (
                    user_request.last_name, user_request.first_name, user_request.email, user_request.role_id,
                    user_request.password))
                await connection.commit()

                return cursor.lastrowid

        except Exception as e:
            print("Error creating user:", e)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)
