from database_connection import DatabaseConnection
from Application.AccountApplication import AccountApplication


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

        # customer_account = await self.account_application.get_customer_account_details(17, 1)
        # print(customer_account)
