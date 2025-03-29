from Dtos.Response.UserResponse import UserResponse
from Service.UserService import UserService
from logger import logger
from Dtos.Request.StaffRequest import StaffRequest
from database_connection import DatabaseConnection
from Service.StaffService import StaffService


class StaffApplication:
    def __init__(self):
        self.database_connection = DatabaseConnection()
        self.user_service = UserService(self.database_connection)
        self.service = StaffService(self.database_connection, self.user_service)

    async def run_application(self):
        # await self.test_database_connection()
        # await self.create_staff("Kim", "Joy", "kim@yopmail.com", "Lead", "obinna")
        await self.get_all_staff()
        # await self.toggle_staff_active_status(1)
        # await self.get_staff_details(1)
        # await self.delete_staff(4)
        # await self.update_staff_details(2, staff_request=StaffRequest(
        #     last_name="Doe",
        #     first_name="John",
        #     email="john.doe@yopmail.com",
        #     position="Lead",
        #     password=None
        # ))

    async def create_staff(self, last_name: str, first_name: str, email: str, position: str, password: str):
        logger.info(f"Attempting to create new staff: {last_name} {first_name}, Email: {email}, Position: {position}")

        staff_request = StaffRequest(
            last_name=last_name,
            first_name=first_name,
            email=email,
            position=position,
            password=password
        )

        new_staff = await self.service.create_staff(staff_request)

        if new_staff:
            logger.info(
                f"Successfully added staff - Id: {new_staff.user_id}, Name: {new_staff.last_name} {new_staff.first_name}, Email: {new_staff.email}, Position: {new_staff.position}")
        else:
            logger.warning(f"Staff with email {email} already exists or an error occurred.")

    async def get_all_staff(self):
        logger.info("Fetching all staff...")
        staff_list = await self.service.get_all_staff()

        if not staff_list:
            logger.warning("No staff records found.")
            return

        for user_response in staff_list:
            print(
                f"User Id: {user_response.user_id}, "
                f"Staff Id: {user_response.staff_id}, "
                f"Name: {user_response.first_name} {user_response.last_name}, "
                f"Email: {user_response.email}, Position: {user_response.position}, "
                f"Role Id: {user_response.role_id}, "
                f"Role: {user_response.role_name}, "
                f"Active: {user_response.active}, "
                f"CreateAt: {user_response.created_at}"
            )
        print()

    async def toggle_staff_active_status(self, user_id: int):
        logger.info(f"Toggling active status for staff with User ID: {user_id}")

        success = await self.service.toggle_staff_active_status(user_id)

        if success:
            print(f"Successfully toggled active status for staff with User ID: {user_id}")
        else:
            logger.warning(f"Failed to toggle active status for staff with User ID: {user_id}")

    async def test_database_connection(self):
        logger.info("Testing database connection...")

        connection = await self.database_connection.get_connection()

        if connection:
            logger.info("Database connection successful.")
            await self.database_connection.release_connection(connection)
        else:
            logger.error("Database connection failed.")

    async def update_staff_details(self, user_id: int, staff_request: StaffRequest):
        logger.info(f"Starting the update of staff with the user id {user_id}")
        result = await self.service.update_staff(user_id, staff_request)

        if result:
            logger.info(f"Staff with User ID {user_id} updated successfully.")
        else:
            logger.warning(f"Failed to update staff with User ID {user_id}.")

        return result

    async def get_staff_details(self, user_id: int) -> UserResponse | None:
        logger.info(f"getting staff details with the user id {user_id}")
        staff = await self.service.get_staff_by_id(user_id)

        if not staff:
            logger.warning(f"Staff with User ID {user_id} not found.")
            return None

        print(
            f"Retrieved Staff Details:\n"
            f"Name: {staff.first_name} {staff.last_name}\n"
            f"User Id: {staff.user_id}\n"
            f"Staff Id: {staff.staff_id}\n"
            f"Email: {staff.email}\n"
            f"Position: {staff.position}\n"
            f"Role: {staff.role_name} (Role Id: {staff.role_id})\n"
            f"Active: {staff.active}\n"
            f"Created At: {staff.created_at}"
        )

        return staff

    async def delete_staff(self, user_id: int):
        logger.info(f"Starting to delete staff with user id {user_id}")
        result = await self.service.delete_staff(user_id)
        if result:
            logger.info(f"Staff {user_id} deleted successfully.")
        else:
            logger.warning(f"Failed to delete staff {user_id}.")
