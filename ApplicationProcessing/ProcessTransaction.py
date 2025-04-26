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

            # customer_account = await self.transaction_application.get_customer_account_details(5, 1)
            # if customer_account:
            #     print(customer_account)
            # else:
            #     print("No customer accounts found.")

            # customer_accounts = await self.transaction_application.get_customer_accounts_with_user_id(6)
            # if customer_accounts:
            #     print(customer_accounts)
            # else:
            #     print("No customer information found.")

            # account_details = await self.transaction_application.get_account_details_by_account_number("2606387058")
            # if account_details:
            #     print(vars(account_details))
            # else:
            #     print("Account not found.")

            # account_balance = await self.transaction_application.get_account_balance_by_account_number("2606387058")
            # if account_balance is not None:
            #     print(f"Account balance: {account_balance}")
            # else:
            #     print("Account not found.")

            fund_account = await self.transaction_application.fund_account("2606387058", 7000)
            if fund_account is not None:
                print(f"Account balance: {fund_account}")
            else:
                print("Account funding failed")

        finally:
            await self.db.dispose()
