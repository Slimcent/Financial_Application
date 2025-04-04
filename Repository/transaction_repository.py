from decimal import Decimal
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.customer import Customer
from models.transaction import Transaction


class TransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_customer_by_id_and_account_type(self, customer_id: int, account_type_id: int) -> Customer:
        result = await self.session.execute(select(Customer).filter_by(Id=customer_id, AccountTypeId=account_type_id))
        return result.scalars().first()

    async def get_accounts_by_customer_id(self, user_id: int) -> List[Customer]:
        result = await self.session.execute(select(Customer).filter_by(UserId=user_id))
        return result.scalars().all()

    async def get_customer_by_id(self, customer_id: int) -> Customer:
        result = await self.session.execute(select(Customer).filter_by(Id=customer_id))
        return result.scalars().first()

    async def create_transaction(self, customer_id: int, account_number: str, amount: Decimal, transaction_type_id: int,
                                 transaction_mode_id: int) -> Transaction:
        new_transaction = Transaction(
            CustomerId=customer_id,
            AccountNumber=account_number,
            Amount=amount,
            TransactionTypeId=transaction_type_id,
            TransactionModeId=transaction_mode_id
        )
        self.session.add(new_transaction)
        await self.session.commit()
        await self.session.refresh(new_transaction)
        return new_transaction

    async def check_account_exists(self, customer_id: int, account_number: str) -> bool:
        result = await self.session.execute(select(Customer).filter_by(Id=customer_id, AccountNumber=account_number))
        return result.scalars().first() is not None
