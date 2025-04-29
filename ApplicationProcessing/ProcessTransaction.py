from Application.TransactionApplication import TransactionApplication
from Dtos.Request.transaction_request import UserTransactionsRequest, TransactionsRequest, FundsTransferRequest
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

            # customer_account = await self.transaction_application.get_customer_account(6, 1)
            # if customer_account:
            #     print(customer_account)
            # else:
            #     print("No customer accounts found.")

            # customer_accounts = await self.transaction_application.get_customer_accounts_with_user_id(6)
            # if customer_accounts:
            #     print(customer_accounts)
            # else:
            #     print("No customer information found.")

            account_details = await self.transaction_application.get_account_details_by_account_number("2606387058")
            if account_details:
                print(vars(account_details))
            else:
                print("Account not found.")

            # account_balance = await self.transaction_application.get_account_balance_by_account_number("2606387058")
            # if account_balance is not None:
            #     print(f"Account balance: {account_balance}")
            # else:
            #     print("Account not found.")

            # fund_account = await self.transaction_application.fund_account("2684681945", 3500)
            # if fund_account is not None:
            #     print(f"Account balance: {fund_account}")
            # else:
            #     print("Account funding failed")

            # user_transactions = await self.transaction_application.get_user_transactions(12)
            # if user_transactions is not None:
            #     print(f"{user_transactions}")
            # else:
            #     print("No transactions found")

            # request = UserTransactionsRequest(
            #     user_id=12,
            #     account_type_id=1,
            #     transaction_type_id=None,
            #     transaction_mode_id=None,
            #     account_number=None,
            #     transaction_status_id=None
            # )
            #
            # filter_user_transactions = await self.transaction_application.filter_user_transactions(request)
            # if filter_user_transactions is not None:
            #     print(f"{filter_user_transactions}")
            # else:
            #     print("No transactions found")

            # request = TransactionsRequest(
            #     user_id=None,
            #     sender_id=None,
            #     account_type_id=None,
            #     transaction_type_id=None,
            #     transaction_mode_id=None,
            #     account_number=None,
            #     transaction_status_id=None,
            #     search_term=None,
            # )
            #
            # all_transactions_paginated = await self.transaction_application.get_all_transactions_paginated(request)
            # if all_transactions_paginated is not None:
            #     print(f"{all_transactions_paginated}")

            # request = TransactionsRequest(
            #     user_id=None,
            #     sender_id=None,
            #     account_type_id=None,
            #     transaction_type_id=None,
            #     transaction_mode_id=None,
            #     account_number=None,
            #     transaction_status_id=None,
            #     search_term=None,
            # )
            #
            # all_transactions_non_paginated = await self.transaction_application.get_all_transactions_non_paginated(request)
            # if all_transactions_non_paginated is not None:
            #     print(f"{all_transactions_non_paginated}")

            # request = FundsTransferRequest(
            #     amount=300,
            #     sender_account_number="2606387058",
            #     receiver_account_number="2684681945",
            #     description="Spencer",
            # )
            #
            # transfer_funds = await self.transaction_application.transfer_funds(request)
            # if transfer_funds is not None:
            #     print(f"{transfer_funds}")

        finally:
            await self.db.dispose()
