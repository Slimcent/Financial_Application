import uuid
import aiomysql
from Infrastructure.Logging.logger import logger
from aiomysql import DictCursor
from Models.Dtos.Request.UserRequest import UserRequest
from Models.Dtos.Request.StaffCreateRequest import StaffCreateRequest
from Models.Dtos.Request.StaffUpdateRequest import StaffUpdateRequest
from Models.Dtos.Response.UserResponse import UserResponse
from Models.Constants.AppConstants import AppConstants
from Data.SqlQueries.staff_sql_queries import STAFF_QUERIES
from Models.Dtos.Request.UpdateUserRequest import UpdateUserRequest
from Data.Extensions.guid import from_db_guid, new_guid, to_db_guid


class StaffService:
    def __init__(self, database_connection, user_service):
        self.database_connection = database_connection
        self.user_service = user_service
        self.constants = AppConstants

    async def create_staff(self, staff_request: StaffCreateRequest):
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
                staff_id = new_guid()  # GUID primary key generated here; the database does not generate it
                await cursor.execute(STAFF_QUERIES["INSERT_NEW_STAFF"],
                                     (to_db_guid(staff_id), to_db_guid(user_id), staff_request.position))
                await connection.commit()

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

    async def toggle_staff_active_status(self, user_id: uuid.UUID):
        logger.info(f"About to call user service to toggle staff status with the user id {user_id}")
        return await self.user_service.toggle_user_active_status(user_id)

    async def update_staff(self, user_id: uuid.UUID, staff_request: StaffUpdateRequest):
        # Built before any database work so an invalid request is raised to the caller
        # instead of being logged as a database failure.
        user_update_request = UpdateUserRequest(
            last_name=staff_request.last_name,
            first_name=staff_request.first_name,
            email=staff_request.email,
        )

        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                # Start a transaction
                await connection.begin()

                # Check if the staff exists
                await cursor.execute(STAFF_QUERIES["GET_STAFF_BY_USER_ID"], (to_db_guid(user_id),))
                staff = await cursor.fetchone()

                if not staff:
                    logger.warning(f"Staff with User Id {user_id} not found.")
                    return None

                logger.info(f"Beginning to update staff {staff['FirstName']} {staff['LastName']}")

                await cursor.execute(STAFF_QUERIES["UPDATE_STAFF"], (staff_request.position, to_db_guid(user_id)))
                logger.info("Staff table updated")

                logger.info("Starting to update staff details in the user table")
                user_updated = await self.user_service.update_user(user_id, user_update_request)

                if not user_updated:
                    logger.error(f"User details for staff with User Id {user_id} could not be updated "
                                 f"(the email address may already be in use). The position change was rolled back.")
                    await connection.rollback()
                    return None

                await connection.commit()

                return True

        except Exception as e:
            logger.error(f"Error updating staff with Id {user_id}: {e}", exc_info=True)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def get_staff_by_id(self, user_id: uuid.UUID) -> UserResponse | None:
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                await cursor.execute(STAFF_QUERIES["GET_STAFF_BY_USER_ID"], (to_db_guid(user_id),))
                staff = await cursor.fetchone()

                if not staff:
                    logger.warning(f"Staff with User Id {user_id} not found.")
                    return None

                user_response = UserResponse(
                    user_id=from_db_guid(staff["Id"]),
                    staff_id=from_db_guid(staff["StaffId"]),
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
            logger.error(f"Error fetching staff with Id {user_id}: {e}", exc_info=True)
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def delete_staff(self, user_id: uuid.UUID):
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                await cursor.execute(STAFF_QUERIES["GET_STAFF_BY_USER_ID"], (to_db_guid(user_id),))
                staff = await cursor.fetchone()

                if not staff:
                    logger.warning(f"Staff with User Id {user_id} not found.")
                    return None

                logger.info(f"Deleting staff {staff['FirstName']} {staff['LastName']} (Id: {user_id})")

                await connection.begin()

                await cursor.execute(STAFF_QUERIES["DELETE_STAFF"], (to_db_guid(user_id),))
                logger.info(f"Staff with user id {user_id} deleted from the staff table")

                logger.info("Starting to delete staff from the user table")
                result = await self.user_service.delete_user(user_id)

                if not result:
                    raise Exception(f"Failed to delete user with Id {user_id}")

                await connection.commit()

                logger.info(f"Staff with user Id {user_id} successfully deleted.")
                return True

        except Exception as e:
            logger.error(f"Error deleting staff with Id {user_id}: {e}", exc_info=True)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)


async def _fetch_staff_data(connection):
    logger.info("attempting to get all staff")
    async with connection.cursor(DictCursor) as cursor:
        query = STAFF_QUERIES["GET_ALL_STAFF"]
        await cursor.execute(query)
        all_staff = await cursor.fetchall()
        logger.info(f"Retrieved {len(all_staff)} staff.")
        return all_staff


def _map_to_user_response(staff_records):
    user_responses = []
    for row in staff_records:
        user_response = UserResponse(
            user_id=from_db_guid(row["UserId"]),
            staff_id=from_db_guid(row["StaffId"]),
            last_name=row["LastName"],
            first_name=row["FirstName"],
            email=row["Email"],
            position=row["Position"],
            role_id=row["RoleId"],
            role_name=row["Name"],
            active=row["Active"] == 1,
            created_at=row["CreatedAt"],
        )
        user_responses.append(user_response)
    return user_responses
