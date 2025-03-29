from aiomysql import DictCursor

from Dtos.Request.UpdateUserRequest import UpdateUserRequest
from logger import logger
import aiomysql
from Dtos.Request.StaffRequest import StaffRequest
from Dtos.Request.UserRequest import UserRequest
from Dtos.Response.UserResponse import UserResponse
from SqlQueries.staff_sql_queries import STAFF_QUERIES
from Infrastructure.AppConstants import AppConstants


async def _fetch_staff_data(connection):
    logger.info("attempting to get all staff")
    async with connection.cursor(DictCursor) as cursor:
        query = STAFF_QUERIES["GET_ALL_STAFF"]
        await cursor.execute(query)
        all_staff = await cursor.fetchall()
        logger.info(f"Retrieved {len(all_staff)} staff.")
        return all_staff


def _map_to_user_response(staff_records):
    """
    Maps the staff data to a list of UserResponse objects.
    """
    user_responses = []
    for row in staff_records:
        user_response = UserResponse(
            user_id=row["Id"],
            staff_id=row["Id"],
            last_name=row["LastName"],
            first_name=row["FirstName"],
            email=row["Email"],
            position=row["Position"],
            role_id=row["RoleId"],
            role_name=row["Name"],
            active=row["Active"] == 1,
            created_at=row["CreatedAt"],
            account_type=None,
            balance=None
        )
        user_responses.append(user_response)
    return user_responses


class StaffService:
    def __init__(self, database_connection, user_service):
        self.database_connection = database_connection
        self.user_service = user_service
        self.constants = AppConstants

    async def create_staff(self, staff_request: StaffRequest):
        logger.info(f"Processing staff creation for {staff_request.email}...")

        user_request = UserRequest(
            first_name=staff_request.first_name,
            last_name=staff_request.last_name,
            email=staff_request.email,
            password=staff_request.password,
            role_id=self.constants.StaffRoleId,
        )

        logger.info("Attempting to create a user first")
        user_id = await self.user_service.create_user(user_request)

        if not user_id:
            logger.error("Failed to create user for staff.")
            return None

        connection = await self.database_connection.get_connection()
        if not connection:
            logger.error("Database connection failed while creating staff.")
            return None

        try:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(STAFF_QUERIES["INSERT_NEW_STAFF"], (user_id, staff_request.position))
                await connection.commit()

                staff_id = cursor.lastrowid
                logger.info(f"New staff created successfully - ID: {staff_id}, Email: {staff_request.email}")

            return UserResponse(
                user_id=user_id,
                last_name=staff_request.last_name,
                first_name=staff_request.first_name,
                email=staff_request.email,
                position=staff_request.position
            )

        except Exception as e:
            logger.error(f"Error creating staff: {e}", exc_info=True)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def get_all_staff(self):
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            staff_records = await _fetch_staff_data(connection)
            user_responses = _map_to_user_response(staff_records)
            return user_responses

        except Exception as e:
            logger.error(f"Error fetching staff records: {e}", exc_info=True)
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def toggle_staff_active_status(self, user_id: int):
        logger.info(f"About to call user service to toggle staff status with the user id {user_id}")
        return await self.user_service.toggle_user_active_status(user_id)

    async def update_staff(self, user_id: int, staff_request: StaffRequest):
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                # Start a transaction
                await connection.begin()

                # Check if the staff exists
                await cursor.execute(STAFF_QUERIES["GET_STAFF_BY_USER_ID"], (user_id,))
                staff = await cursor.fetchone()

                if not staff:
                    logger.warning(f"Staff with User Id {user_id} not found.")
                    return None

                logger.info(f"Beginning to update staff {staff['FirstName']} {staff['LastName']}")

                await cursor.execute(STAFF_QUERIES["UPDATE_STAFF"], (staff_request.position, user_id))
                logger.info("Staff table updated")

                logger.info("Starting to update staff details in the user table")
                user_update_request = UpdateUserRequest(
                    last_name=staff_request.last_name,
                    first_name=staff_request.first_name,
                    email=staff_request.email,
                )
                await self.user_service.update_user(user_id, user_update_request)

                # Commit the transaction
                await connection.commit()

                return True

        except Exception as e:
            logger.error(f"Error updating staff with ID {user_id}: {e}", exc_info=True)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def get_staff_by_id(self, user_id: int) -> UserResponse | None:
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                await cursor.execute(STAFF_QUERIES["GET_STAFF_BY_USER_ID"], (user_id,))
                staff = await cursor.fetchone()

                if not staff:
                    logger.warning(f"Staff with User Id {user_id} not found.")
                    return None

                user_response = UserResponse(
                    user_id=staff["Id"],
                    staff_id=staff["StaffId"],
                    last_name=staff["LastName"],
                    first_name=staff["FirstName"],
                    email=staff["Email"],
                    position=staff["Position"],
                    role_id=staff["RoleId"],
                    role_name=staff["Name"],
                    active=staff["Active"] == 1,
                    created_at=staff["CreatedAt"] if staff["CreatedAt"] else None,
                )

                return user_response

        except Exception as e:
            logger.error(f"Error fetching staff with ID {user_id}: {e}", exc_info=True)
            return None

        finally:
            await self.database_connection.release_connection(connection)
