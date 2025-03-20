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
