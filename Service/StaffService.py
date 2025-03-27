import aiomysql
from Dtos.Request.StaffRequest import StaffRequest
from Dtos.Request.UserRequest import UserRequest


class StaffService:
    def __init__(self, database_connection, user_service):
        self.database_connection = database_connection
        self.user_service = user_service

    async def create_staff(self, staff_request: StaffRequest):
        user_request = UserRequest(
            name=staff_request.name,
            email=staff_request.email,
            role_id=2,
        )

        user_id = await self.user_service.create_user(user_request)

        if not user_id:
            raise ValueError("Failed to create user for staff")

        connection = await self.database_connection.connect()
        if not connection:
            return None

        async with connection.cursor() as cursor:
            insert_query = """
                    INSERT INTO Staff (UserId, Position) 
                    VALUES (%s, %s)
                    """
            await cursor.execute(insert_query, (user_id, staff_request.position))
            await connection.commit()

            staff_id = cursor.lastrowid

        await connection.ensure_closed()
        return staff_id
