from Dtos.Request.AccountTypeRequest import AccountTypeRequest
from Dtos.Response.AccountTypeResponse import AccountTypeResponse


class AccountTypeService:
    def __init__(self, _database_connection):
        self.database_connection = _database_connection

    def get_all_account_types(self):
        connection = self.database_connection.connect()
        if not connection:
            return []

        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM AccountTypes")
        account_types = cursor.fetchall()
        cursor.close()
        self.database_connection.close()

        return [
            AccountTypeResponse(account_type_id=row["Id"], name=row["Type"])
            for row in account_types
        ]

    def get_account_type_by_id(self, account_type_id: int):
        connection = self.database_connection.connect()
        if not connection:
            return None

        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM AccountTypes WHERE Id = %s", (account_type_id,))
        account_type = cursor.fetchone()
        cursor.close()
        self.database_connection.close()

        if account_type:
            return AccountTypeResponse(
                account_type_id=account_type["Id"],
                name=account_type["Type"]
            )
        return None

    def add_account_type(self, request: AccountTypeRequest):
        connection = self.database_connection.connect()
        if not connection:
            return None

        try:
            cursor = connection.cursor(dictionary=True)

            # Check if the name already exists
            check_query = "SELECT * FROM AccountTypes WHERE Type = %s"
            cursor.execute(check_query, (request.name,))
            existing_account_type = cursor.fetchone()

            if existing_account_type:
                print("Account type already exists")
                return None

            # Insert new account type
            insert_query = "INSERT INTO AccountTypes (Type) VALUES (%s)"
            cursor.execute(insert_query, (request.name,))
            connection.commit()

            new_id = cursor.lastrowid
            return AccountTypeResponse(account_type_id=new_id, name=request.name)

        except Exception as e:
            print("Error adding account type:", e)
            connection.rollback()
            return None

        finally:
            cursor.close()
            self.database_connection.close()

    def update_account_type(self, account_type_id: int, request: AccountTypeRequest):
        connection = self.database_connection.connect()
        if not connection:
            return None

        try:
            cursor = connection.cursor(dictionary=True)

            # Check if the account type exists
            check_query = "SELECT * FROM AccountTypes WHERE Id = %s"
            cursor.execute(check_query, (account_type_id,))
            existing_account_type = cursor.fetchone()

            if not existing_account_type:
                print("Account type not found")
                return None

            # Update the account type
            update_query = "UPDATE AccountTypes SET Type = %s WHERE Id = %s"
            cursor.execute(update_query, (request.name, account_type_id))
            connection.commit()

            return AccountTypeResponse(account_type_id=account_type_id, name=request.name)

        except Exception as e:
            print("Error updating account type:", e)
            connection.rollback()
            return None

        finally:
            cursor.close()
            self.database_connection.close()

    def delete_account_type(self, account_type_id: int):
        connection = self.database_connection.connect()
        if not connection:
            return False

        try:
            cursor = connection.cursor(dictionary=True)

            # Check if the account type exists
            check_query = "SELECT * FROM AccountTypes WHERE Id = %s"
            cursor.execute(check_query, (account_type_id,))
            existing_account_type = cursor.fetchone()

            if not existing_account_type:
                print("Account type not found")
                return False  # Return False if not found

            # Delete the account type
            delete_query = "DELETE FROM AccountTypes WHERE Id = %s"
            cursor.execute(delete_query, (account_type_id,))
            connection.commit()

            print(f"Account type with ID {account_type_id} deleted successfully")
            return True

        except Exception as e:
            print("Error deleting account type:", e)
            connection.rollback()
            return False

        finally:
            cursor.close()
            self.database_connection.close()

