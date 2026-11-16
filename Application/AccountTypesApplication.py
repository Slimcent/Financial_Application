from Data.Interfaces.i_unit_of_work import UnitOfWorkFactory
from Infrastructure.Logging.logger import logger
from Models.Dtos.Request.AccountTypeRequest import AccountTypeRequest
from Models.Entities import Role
from Services.Exceptions.domain_exceptions import ServiceError
from Services.Interfaces.i_account_type_service import IAccountTypeService


class AccountTypesApplication:
    def __init__(self, unit_of_work_factory: UnitOfWorkFactory, account_type_service: IAccountTypeService):
        self.unit_of_work_factory = unit_of_work_factory
        self.service = account_type_service

    async def run_application(self):
        # await self.test_database_connection()

        await self.get_all_account_types()
        # await self.get_account_type_by_id(1)
        # await self.create_account_type("Retirement")
        # await self.update_account_type(5, "Updated Retirement")
        # await self.delete_account_type(5)

    async def get_all_account_types(self):
        logger.info("Fetching all account types...")
        async with self.unit_of_work_factory() as unit_of_work:
            account_types = await self.service.get_all_account_types(unit_of_work)

        if not account_types:
            logger.warning("No account types found.")
        for account in account_types:
            print(f"Id: {account.account_type_id}, Name: {account.name}")
        print()

    async def get_account_type_by_id(self, account_type_id: int):
        logger.info(f"Fetching account type with Id: {account_type_id}")
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                account_type = await self.service.get_account_type_by_id(unit_of_work, account_type_id)
        except ServiceError as error:
            logger.warning(error.message)
        else:
            print(f"Account Type Found: Id: {account_type.account_type_id}, Name: {account_type.name}")
        print()

    async def create_account_type(self, name: str):
        logger.info(f"Creating new account type with name: {name}")
        account_type_request = AccountTypeRequest(name=name)
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                new_account_type = await self.service.add_account_type(unit_of_work, account_type_request)
        except ServiceError as error:
            logger.warning(error.message)
        else:
            print(f"New Account Type Added - Id: {new_account_type.account_type_id}, Name: {new_account_type.name}")
        print()

    async def update_account_type(self, account_type_id: int, name: str):
        logger.info(f"Updating account type with Id: {account_type_id}, New Name: {name}")
        update_request = AccountTypeRequest(name=name)
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                updated_account = await self.service.update_account_type(unit_of_work, account_type_id,
                                                                         update_request)
        except ServiceError as error:
            logger.warning(error.message)
        else:
            print(f"Account Type Updated - ID: {updated_account.account_type_id}, Name: {updated_account.name}")
        print()

    async def delete_account_type(self, account_type_id: int):
        logger.info(f"Attempting to delete account type with Id: {account_type_id}")
        try:
            async with self.unit_of_work_factory() as unit_of_work:
                await self.service.delete_account_type(unit_of_work, account_type_id)
        except ServiceError as error:
            logger.warning(error.message)
        else:
            print("Account type deleted successfully.")
        print()

    async def test_database_connection(self):
        logger.info("Testing database connection...")

        try:
            async with self.unit_of_work_factory() as unit_of_work:
                await unit_of_work.roles.exists_async(Role.Id > 0)
        except Exception as error:
            logger.error(f"Database connection failed: {error}")
        else:
            print("Database connection successful.")
