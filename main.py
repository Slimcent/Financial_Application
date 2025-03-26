from Dtos.Request.AccountTypeRequest import AccountTypeRequest
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

# account_types = service.get_all_account_types()
# for account in account_types:
#     print(f"Id: {account.account_type_id}, Name: {account.name}")
#
# print()
#
# account_type = service.get_account_type_by_id(1)
# if account_type:
#     print(f"Account Type Found: Id: {account_type.account_type_id}, Name: {account_type.name}")
# else:
#     print("Account type not found.")
#
# print()

# # Create a request object
# account_type_request = AccountTypeRequest(name="Business")
#
# # Add a new account type
# new_account_type = service.add_account_type(account_type_request)
#
# # Check the result
# if new_account_type:
#     print(f"New Account Type Added - Id: {new_account_type.account_type_id}, Name: {new_account_type.name}")
# else:
#     print("Account type already exists or an error occurred")


# Create a request object for update
update_request = AccountTypeRequest(name="Updated Business")

# Call the update method
updated_account = service.update_account_type(3, update_request)

if updated_account:
    print(f"Account Type Updated - ID: {updated_account.account_type_id}, Name: {updated_account.name}")
else:
    print("Account type not found or update failed")

# delete = service.delete_account_type(5)
#
# if delete:
#     print("Account type deleted successfully")
# else:
#     print("Account type not found or delete failed")
