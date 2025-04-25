from Application.TransactionApplication import TransactionApplication
from Repository.transaction_repository import TransactionRepository
from Service.TransactionService import TransactionService
from database_orm_async import Database


class ProcessTransaction:
    def __init__(self):
        transaction_repo = TransactionRepository()
        transaction_service = TransactionService(transaction_repo)
        self.transaction_application = TransactionApplication(transaction_repo, transaction_service)
        self.db = Database()

    async def run_application(self):
        try:
            print("Beginning transaction process")

            customer_accounts = await self.transaction_application.get_customer_account_details(5, 1)
            if customer_accounts:
                print(customer_accounts)
            else:
                print("No customer accounts found.")

        finally:
            await self.db.dispose()
