import logging
import aiomysql
from Dtos.Request.StaffRequest import StaffRequest
from Dtos.Request.UserRequest import UserRequest
from Infrastructure import AppConstants
from SqlQueries.staff_sql_queries import STAFF_QUERIES


class StaffService:
    def __init__(self, database_connection, user_service, constants: AppConstants):
        self.database_connection = database_connection
        self.user_service = user_service
        self.constants = constants

    async def create_staff(self, staff_request: StaffRequest):
        user_request = UserRequest(
            first_name=staff_request.first_name,
            last_name=staff_request.last_name,
            email=staff_request.email,
            password=staff_request.password,
            role_id=self.constants.StaffRoleId,
        )

        user_id = await self.user_service.create_user(user_request)

        if not user_id:
            raise ValueError("Failed to create user for staff")

        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(STAFF_QUERIES["INSERT_NEW_STAFF"], (user_id, staff_request.position))
                await connection.commit()

                staff_id = cursor.lastrowid

            return staff_id

        except Exception as e:
            logging.error(f"Error creating staff: {e}", exc_info=True)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)
