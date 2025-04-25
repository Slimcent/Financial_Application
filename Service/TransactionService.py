from Dtos.Response.AccountResponse import AccountResponse
from Dtos.Response.AccountsResponse import AccountsResponse
from Repository.transaction_repository import TransactionRepository


class TransactionService:
    def __init__(self, transaction_repo: TransactionRepository):
        self.transaction_repo = transaction_repo

    async def get_customer_account_details(self, customer_id: int, account_type_id: int) -> AccountResponse:
        print("Transaction service")
        account = await self.transaction_repo.get_account_by_customer_and_type(customer_id, account_type_id)

        if not account:
            raise ValueError("Account not found.")

        print("Done with repo")
        customer = account.customer
        user = customer.user

        account_response = AccountsResponse(
            account_id=account.Id,
            account_number=account.AccountNumber,
            balance=float(account.Balance),
            account_type=account.account_type.Type,
            account_type_id=account.AccountTypeId
        )

        print("Finished mapping")

        return AccountResponse(
            user_id=user.Id,
            customer_id=customer.Id,
            last_name=user.LastName,
            first_name=user.FirstName,
            email=user.Email,
            accounts=[account_response],
            balance=float(account.Balance)
        )
