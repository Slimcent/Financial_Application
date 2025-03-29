from SqlQueries.account_type_sql_queries import ACCOUNT_TYPE_QUERIES
from logger import logger
from aiomysql import DictCursor
from Dtos.Request.AccountTypeRequest import AccountTypeRequest
from Dtos.Response.AccountTypeResponse import AccountTypeResponse


class AccountTypeService:
    def __init__(self, _database_connection):
        self.database_connection = _database_connection

    async def get_all_account_types(self):
        try:
            connection = await self.database_connection.get_connection()
            if not connection:
                logger.error("Failed to get database connection in get_all_account_types.")
                return []

            async with connection.cursor(DictCursor) as cursor:
                logger.info("Executing query: SELECT * FROM AccountTypes")
                await cursor.execute(ACCOUNT_TYPE_QUERIES["SELECT_ALL_ACCOUNT_TYPES"])
                account_types = await cursor.fetchall()

            await self.database_connection.release_connection(connection)

            logger.info(f"Retrieved {len(account_types)} account types.")
            return [
                AccountTypeResponse(account_type_id=row["Id"], name=row["Type"])
                for row in account_types
            ]
        except Exception as e:
            logger.error(f"Error in get_all_account_types: {e}")
            return []

    async def get_account_type_by_id(self, account_type_id: int):
        try:
            connection = await self.database_connection.get_connection()
            if not connection:
                logger.error("Failed to get database connection in get_account_type_by_id.")
                return None

            async with connection.cursor(DictCursor) as cursor:
                logger.info(f"Executing query: SELECT * FROM AccountTypes WHERE Id = {account_type_id}")
                await cursor.execute(ACCOUNT_TYPE_QUERIES["SELECT_ACCOUNT_TYPE_BY_ID"], (account_type_id,))
                account_type = await cursor.fetchone()

            await self.database_connection.release_connection(connection)

            if account_type:
                logger.info(f"Account type found: {account_type['Type']}")
                return AccountTypeResponse(
                    account_type_id=account_type["Id"],
                    name=account_type["Type"]
                )
            else:
                logger.warning(f"Account type with ID {account_type_id} not found.")
                return None
        except Exception as e:
            logger.error(f"Error in get_account_type_by_id: {e}")
            return None

    async def add_account_type(self, request: AccountTypeRequest):
        try:
            connection = await self.database_connection.get_connection()
            if not connection:
                logger.error("Failed to get database connection in add_account_type.")
                return None

            async with connection.cursor(DictCursor) as cursor:
                # Check if the name already exists
                logger.info(f"Checking if account type '{request.name}' already exists.")
                await cursor.execute(ACCOUNT_TYPE_QUERIES["SELECT_ACCOUNT_TYPE_BY_NAME"], (request.name,))
                existing_account_type = await cursor.fetchone()

                if existing_account_type:
                    logger.warning(f"Account type '{request.name}' already exists.")
                    return None

                # Insert new account type
                logger.info(f"Inserting new account type: {request.name}")
                await cursor.execute(ACCOUNT_TYPE_QUERIES["INSERT_ACCOUNT_TYPE"], (request.name,))
                await connection.commit()

                new_id = cursor.lastrowid
                logger.info(f"New account type added with ID {new_id}")
                return AccountTypeResponse(account_type_id=new_id, name=request.name)

        except Exception as e:
            logger.error(f"Error adding account type '{request.name}': {e}")
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def update_account_type(self, account_type_id: int, request: AccountTypeRequest):
        try:
            connection = await self.database_connection.get_connection()
            if not connection:
                logger.error("Failed to get database connection in update_account_type.")
                return None

            async with connection.cursor(DictCursor) as cursor:
                # Check if the account type exists
                logger.info(f"Checking if account type with ID {account_type_id} exists.")
                await cursor.execute(ACCOUNT_TYPE_QUERIES["SELECT_ACCOUNT_TYPE_BY_ID"], (account_type_id,))
                existing_account_type = await cursor.fetchone()

                if not existing_account_type:
                    logger.warning(f"Account type with ID {account_type_id} not found.")
                    return None

                # Update the account type
                logger.info(f"Updating account type with ID {account_type_id} to '{request.name}'")
                await cursor.execute(ACCOUNT_TYPE_QUERIES["UPDATE_ACCOUNT_TYPE"], (request.name, account_type_id))
                await connection.commit()

                logger.info(f"Account type with ID {account_type_id} updated successfully.")
                return AccountTypeResponse(account_type_id=account_type_id, name=request.name)

        except Exception as e:
            logger.error(f"Error updating account type with ID {account_type_id}: {e}")
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def delete_account_type(self, account_type_id: int):
        try:
            connection = await self.database_connection.get_connection()
            if not connection:
                logger.error("Failed to get database connection in delete_account_type.")
                return False

            async with connection.cursor(DictCursor) as cursor:
                # Check if the account type exists
                logger.info(f"Checking if account type with ID {account_type_id} exists.")
                await cursor.execute(ACCOUNT_TYPE_QUERIES["SELECT_ACCOUNT_TYPE_BY_ID"], (account_type_id,))
                existing_account_type = await cursor.fetchone()

                if not existing_account_type:
                    logger.warning(f"Account type with ID {account_type_id} not found.")
                    return False

                # Delete the account type
                logger.info(f"Deleting account type with ID {account_type_id}")
                await cursor.execute(ACCOUNT_TYPE_QUERIES["DELETE_ACCOUNT_TYPE"], (account_type_id,))
                await connection.commit()

                logger.info(f"Account type with ID {account_type_id} deleted successfully.")
                return True

        except Exception as e:
            logger.error(f"Error deleting account type with ID {account_type_id}: {e}")
            await connection.rollback()
            return False

        finally:
            await self.database_connection.release_connection(connection)
