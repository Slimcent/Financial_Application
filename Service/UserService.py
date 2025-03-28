from aiomysql import DictCursor
from Dtos.Request.UserRequest import UserRequest
from Utility.Security import hash_password


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

                # Hash the password before inserting it
                hashed_password = hash_password(user_request.password)

                # Insert new user
                insert_query = "INSERT INTO Users (LastName, FirstName, Email, RoleId, Password) VALUES (%s, %s, %s, " \
                               "%s, %s) "
                await cursor.execute(insert_query, (
                    user_request.last_name, user_request.first_name, user_request.email, user_request.role_id,
                    hashed_password))
                await connection.commit()

                return cursor.lastrowid

        except Exception as e:
            print("Error creating user:", e)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)
