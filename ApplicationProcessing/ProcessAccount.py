import uuid
from Data.database_connection import DatabaseConnection
from Application.AccountApplication import AccountApplication

# Placeholder for the demo calls below: replace with a real Users.Id (GUID) from your database.
SAMPLE_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


class ProcessAccount:
    def __init__(self):
        self.database_connection = DatabaseConnection()
        self.account_application = AccountApplication(self.database_connection)

    async def run_application(self):
        customer_accounts = await self.account_application.get_all_customer_accounts()
        if customer_accounts:
            for customer in customer_accounts:
                print(customer)
        print()

        # customer_account = await self.account_application.get_customer_account_details(SAMPLE_USER_ID, 1)
        # print(customer_account)
