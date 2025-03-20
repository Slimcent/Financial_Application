from database_connection import DatabaseConnection
from Service.AccountTypeService import AccountTypeService

# Create an instance of DatabaseConnection
db_connection = DatabaseConnection()

# Attempt to connect
connection = db_connection.connect()

if connection:
    print("Database connection successful!")
else:
    print("Failed to connect to the database.")

service = AccountTypeService(db_connection)
account_types = service.get_all_account_types()
for account in account_types:
    print(f"Id: {account.account_type_id}, Name: {account.name}")


print()


account_type = service.get_account_type_by_id(1)
if account_type:
    print(f"Account Type Found: Id: {account_type.account_type_id}, Name: {account_type.name}")
else:
    print("Account type not found.")

