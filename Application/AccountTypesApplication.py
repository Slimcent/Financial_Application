import asyncio
from logger import logger
from database_connection import DatabaseConnection
from Service.AccountTypeService import AccountTypeService
from Dtos.Request.AccountTypeRequest import AccountTypeRequest


class AccountTypesApplication:
    def __init__(self):
        self.database_connection = DatabaseConnection()
        self.service = AccountTypeService(self.database_connection)

    async def run_application(self):
        # await self.test_database_connection()

        await self.get_all_account_types()
        # await self.get_account_type_by_id(1)
        # await self.create_account_type("Retirement")
        # await self.update_account_type(5, "Updated Retirement")
        # await self.delete_account_type(5)

    async def get_all_account_types(self):
        logger.info("Fetching all account types...")
        account_types = await self.service.get_all_account_types()
        if not account_types:
            logger.warning("No account types found.")
        for account in account_types:
            print(f"Id: {account.account_type_id}, Name: {account.name}")
        print()

    async def get_account_type_by_id(self, account_type_id: int):
        logger.info(f"Fetching account type with Id: {account_type_id}")
        account_type = await self.service.get_account_type_by_id(account_type_id)
        if account_type:
            print(f"Account Type Found: Id: {account_type.account_type_id}, Name: {account_type.name}")
        else:
            logger.warning(f"Account type with Id {account_type_id} not found.")
        print()

    async def create_account_type(self, name: str):
        logger.info(f"Creating new account type with name: {name}")
        account_type_request = AccountTypeRequest(name=name)
        new_account_type = await self.service.add_account_type(account_type_request)

        if new_account_type:
            print(f"New Account Type Added - Id: {new_account_type.account_type_id}, Name: {new_account_type.name}")
        else:
            logger.warning(f"Account type with name {name} already exists or an error occurred.")
        print()

    async def update_account_type(self, account_type_id: int, name: str):
        logger.info(f"Updating account type with Id: {account_type_id}, New Name: {name}")
        update_request = AccountTypeRequest(name=name)
        updated_account = await self.service.update_account_type(account_type_id, update_request)

        if updated_account:
            print(f"Account Type Updated - ID: {updated_account.account_type_id}, Name: {updated_account.name}")
        else:
            logger.warning(f"Account type with Id {account_type_id} not found or update failed.")
        print()

    async def delete_account_type(self, account_type_id: int):
        logger.info(f"Attempting to delete account type with Id: {account_type_id}")
        deleted = await self.service.delete_account_type(account_type_id)

        if deleted:
            print("Account type deleted successfully.")
        else:
            logger.warning(f"Account type with ID {account_type_id} not found or delete failed.")
        print()

    async def test_database_connection(self):
        logger.info("Testing database connection...")

        connection = await self.database_connection.get_connection()

        if connection:
            print("Database connection successful.")
            await self.database_connection.release_connection(connection)  # Release the connection if successful
        else:
            logger.error("Database connection failed.")


# Main function to run the application
# async def main():
#     app = AccountTypesApplication()
#     await app.run_application()
#
#
# # Entry point of the program
# if __name__ == "__main__":
#     asyncio.run(main())
