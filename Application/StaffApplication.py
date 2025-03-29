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
        # await self.create_staff("Koke", "Bula", "bula@yopmail.com", "Engineer", "obinna")
        # await self.get_all_staff()
        await self.toggle_staff_active_status(1)

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
            print("Database connection successful.")
            await self.database_connection.release_connection(connection)
        else:
            logger.error("Database connection failed.")
