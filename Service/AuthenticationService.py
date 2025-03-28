from aiomysql import DictCursor
from Utility.Security import verify_password


async def login_user(self, email: str, password: str):
    connection = await self.database_connection.get_connection()
    if not connection:
        return None

    try:
        async with connection.cursor(DictCursor) as cursor:
            query = "SELECT Id, Password FROM Users WHERE Email = %s"
            await cursor.execute(query, (email,))
            user = await cursor.fetchone()

            if user and verify_password(password, user["Password"]):
                print("Login successful!")
                return user["Id"]

            print("Invalid email or password")
            return None

    finally:
        await self.database_connection.release_connection(connection)
