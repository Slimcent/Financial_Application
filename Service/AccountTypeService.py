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
                print("Failed to get connection.")
                return []

            async with connection.cursor(DictCursor) as cursor:
                await cursor.execute("SELECT * FROM AccountTypes")  # Main query
                account_types = await cursor.fetchall()

            await self.database_connection.release_connection(connection)

            return [
                AccountTypeResponse(account_type_id=row["Id"], name=row["Type"])
                for row in account_types
            ]
        except Exception as e:
            print(f"Error in get_all_account_types: {e}")
            return []

    async def get_account_type_by_id(self, account_type_id: int):
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        async with connection.cursor(DictCursor) as cursor:
            await cursor.execute("SELECT * FROM AccountTypes WHERE Id = %s", (account_type_id,))
            account_type = await cursor.fetchone()

        await self.database_connection.release_connection(connection)

        if account_type:
            return AccountTypeResponse(
                account_type_id=account_type["Id"],
                name=account_type["Type"]
            )
        return None

    async def add_account_type(self, request: AccountTypeRequest):
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                # Check if the name already exists
                check_query = "SELECT * FROM AccountTypes WHERE Type = %s"
                await cursor.execute(check_query, (request.name,))
                existing_account_type = await cursor.fetchone()

                if existing_account_type:
                    print("Account type already exists")
                    return None

                # Insert new account type
                insert_query = "INSERT INTO AccountTypes (Type) VALUES (%s)"
                await cursor.execute(insert_query, (request.name,))
                await connection.commit()

                new_id = cursor.lastrowid
                return AccountTypeResponse(account_type_id=new_id, name=request.name)

        except Exception as e:
            print("Error adding account type:", e)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def update_account_type(self, account_type_id: int, request: AccountTypeRequest):
        connection = await self.database_connection.get_connection()
        if not connection:
            return None

        try:
            async with connection.cursor(DictCursor) as cursor:
                # Check if the account type exists
                check_query = "SELECT * FROM AccountTypes WHERE Id = %s"
                await cursor.execute(check_query, (account_type_id,))
                existing_account_type = await cursor.fetchone()

                if not existing_account_type:
                    print("Account type not found")
                    return None

                # Update the account type
                update_query = "UPDATE AccountTypes SET Type = %s WHERE Id = %s"
                await cursor.execute(update_query, (request.name, account_type_id))
                await connection.commit()

                return AccountTypeResponse(account_type_id=account_type_id, name=request.name)

        except Exception as e:
            print("Error updating account type:", e)
            await connection.rollback()
            return None

        finally:
            await self.database_connection.release_connection(connection)

    async def delete_account_type(self, account_type_id: int):
        connection = await self.database_connection.get_connection()
        if not connection:
            return False

        try:
            async with connection.cursor(DictCursor) as cursor:
                # Check if the account type exists
                check_query = "SELECT * FROM AccountTypes WHERE Id = %s"
                await cursor.execute(check_query, (account_type_id,))
                existing_account_type = await cursor.fetchone()

                if not existing_account_type:
                    print("Account type not found")
                    return False

                # Delete the account type
                delete_query = "DELETE FROM AccountTypes WHERE Id = %s"
                await cursor.execute(delete_query, (account_type_id,))
                await connection.commit()

                print(f"Account type with ID {account_type_id} deleted successfully")
                return True

        except Exception as e:
            print("Error deleting account type:", e)
            await connection.rollback()
            return False

        finally:
            await self.database_connection.release_connection(connection)
