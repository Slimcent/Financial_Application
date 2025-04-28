from decimal import Decimal

from Dtos.Request.transaction_request import TransactionRequest
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

    async def get_customer_account(self, user_id: int, account_type_id: int):
        async with self.db.get_session() as session:
            result = await session.execute(
                select(Account)
                .options(
                    joinedload(Account.user).joinedload(User.customer),
                    joinedload(Account.account_type)
                )
                .filter(
                    Account.UserId == user_id,
                    Account.AccountTypeId == account_type_id
                )
            )

            return result.scalars().first()

    async def get_customer_accounts_with_user_id(self, user_id: int) -> Optional[User]:
        async with self.db.get_session() as session:
            stmt = (
                select(User)
                .options(
                    joinedload(User.accounts).joinedload(Account.account_type),
                    joinedload(User.customer)
                )
                .filter(User.Id == user_id)
            )
            result = await session.execute(stmt)
            return result.scalars().first()

    async def get_account_by_account_number(self, account_number: str) -> Optional[Account]:
        async with self.db.get_session() as session:
            stmt = (
                select(Account)
                .options(
                    joinedload(Account.account_type),
                    joinedload(Account.user).joinedload(User.customer)
                )
                .filter(Account.AccountNumber == account_number)
            )
            result = await session.execute(stmt)
            return result.scalars().first()

    async def update_account_balance(self, account: Account, amount: float, session=None):
        try:
            account.Balance += amount
            if session is None:
                async with self.db.get_session() as session:
                    session.add(account)
                    await session.commit()
                    return account
            else:
                session.add(account)
                return account
        except Exception as e:
            print(f"Update balance error: {e}")
            raise

    async def create_transaction(self, transaction_request: TransactionRequest, session=None):
        try:
            transaction = Transaction(
                UserId = transaction_request.user_id,
                AccountId=transaction_request.account_id,
                TransactionTypeId=transaction_request.transaction_type_id,
                TransactionModeId=transaction_request.transaction_mode_id,
                TransactionStatusId=transaction_request.transaction_status_id,
                Amount=transaction_request.amount,
                SenderId=transaction_request.sender_id,
                Description=transaction_request.description
            )

            if session is None:
                async with self.db.get_session() as session:
                    session.add(transaction)
                    await session.commit()
            else:
                session.add(transaction)
        except Exception as e:
            print(f"Transaction creation failed: {e}")
            raise

    async def get__all_user_transactions(self, user_id: int) -> List[Transaction]:
        async with self.db.get_session() as session:
            stmt = (
                select(Transaction)
                .options(
                    joinedload(Transaction.account).joinedload(Account.account_type),
                    joinedload(Transaction.transaction_type),
                    joinedload(Transaction.transaction_mode),
                    joinedload(Transaction.transaction_status),
                    joinedload(Transaction.user).joinedload(User.customer),
                    joinedload(Transaction.user).joinedload(User.Staff),
                )
                .filter(Transaction.UserId == user_id)
                .order_by(Transaction.TransactionDate.desc())
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_user_transactions(self, user_id: int) -> User:
        async with self.db.get_session() as session:
            stmt = (
                select(User)
                .options(
                    joinedload(User.customer),
                    joinedload(User.Staff),
                    joinedload(User.transactions)
                    .joinedload(Transaction.account)
                    .joinedload(Account.account_type),
                    joinedload(User.transactions)
                    .joinedload(Transaction.transaction_type),
                    joinedload(User.transactions)
                    .joinedload(Transaction.transaction_mode),
                    joinedload(User.transactions)
                    .joinedload(Transaction.transaction_status),
                )
                .filter(User.Id == user_id)
            )
            result = await session.execute(stmt)
            return result.scalars().first()
