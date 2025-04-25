from decimal import Decimal
from models.user import User
from models.Roles import Role
from sqlalchemy import select
from models.Staff import Staff
from typing import List, Optional
from models.accounts import Account
from models.customer import Customer
from database_orm_async import Database
from models.transaction import Transaction
from models.account_type import AccountType
from models.transaction_type import TransactionType
from sqlalchemy.orm import selectinload, joinedload
from models.transaction_mode import TransactionMode
from models.transaction_status import TransactionStatus


class TransactionRepository:
    def __init__(self):
        self.db = Database()

    async def get_customer_accounts(self, customer_id: int, account_type_id: int):
        print("Trying to connect to the database")
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Account)
                .options(
                    joinedload(Account.customer).joinedload(Customer.user),
                    joinedload(Account.account_type)
                )
                .filter(
                    Account.CustomerId == customer_id,
                    Account.AccountTypeId == account_type_id
                )
            )

            print("Done getting data")
            return result.scalars().first()

    async def get_customer_accounts_with_user_id(self, user_id: int) -> Optional[Customer]:
        async with self.db.get_session() as session:
            stmt = (
                select(Customer)
                .options(
                    joinedload(Customer.accounts).joinedload(Account.account_type),
                    joinedload(Customer.user)
                )
                .filter(Customer.UserId == user_id)
            )
            result = await session.execute(stmt)
            return result.scalars().first()
