import database_connection
from Application.AccountApplication import AccountApplication
from Service.AccountService import AccountService
from database_connection import DatabaseConnection


class ProcessAccount:
    def __init__(self):
        self.database_connection = DatabaseConnection()
        self.account_service = AccountService(database_connection)
        self.account_application = AccountApplication()

    async def run_application(self):
        customer_accounts = await self.account_application.get_all_customer_accounts()
        if customer_accounts:
            for customer in customer_accounts:
                print(customer)
