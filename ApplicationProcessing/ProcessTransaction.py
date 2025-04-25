from Application.TransactionApplication import TransactionApplication
from Repository.transaction_repository import TransactionRepository
from Service.transaction_service import TransactionService
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

            # customer_accounts = await self.transaction_application.get_customer_account_details(5, 1)
            # if customer_accounts:
            #     print(customer_accounts)
            # else:
            #     print("No customer accounts found.")

            customer_data = await self.transaction_application.get_customer_accounts_with_user_id(5)
            if customer_data:
                print(customer_data)
            else:
                print("No customer information found.")

        finally:
            await self.db.dispose()
