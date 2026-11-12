import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from Models.Entities.base_entity import LAZY, BaseEntity
from Models.Entities.column_types import GUID, uuid7

if TYPE_CHECKING:
    from Models.Entities.account_type import AccountType
    from Models.Entities.transaction import Transaction
    from Models.Entities.user import User


class Account(BaseEntity):
    __tablename__ = "Accounts"

    Id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid7)
    UserId: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("Users.Id", ondelete="RESTRICT"))
    AccountTypeId: Mapped[int] = mapped_column(Integer, ForeignKey("AccountTypes.Id", ondelete="RESTRICT"),
                                               index=True)
    AccountNumber: Mapped[str] = mapped_column(String(10), unique=True)
    # A balance accumulates many transaction amounts, so it has more whole digits than a single
    # Transactions.Amount (DECIMAL(10, 2)): up to 9,999,999,999,999,999.99.
    Balance: Mapped[Decimal] = mapped_column(DECIMAL(18, 2), default=Decimal("0.00"), server_default="0.00")

    user: Mapped["User"] = relationship(back_populates="accounts", lazy=LAZY)
    # Joined on AccountId only (Transactions also has a composite foreign key to (Id, UserId)).
    # An account with transactions cannot be deleted (ON DELETE RESTRICT).
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account", lazy=LAZY,
                                                             passive_deletes="all",
                                                             primaryjoin="Account.Id == Transaction.AccountId",
                                                             foreign_keys="Transaction.AccountId")
    account_type: Mapped["AccountType"] = relationship(back_populates="accounts", lazy=LAZY)

    __table_args__ = (
        # one account per account type for each user; also serves as the index for the UserId foreign key
        UniqueConstraint("UserId", "AccountTypeId"),
        # target of the Transactions (AccountId, UserId) foreign key: a transaction's user owns its account
        UniqueConstraint("Id", "UserId"),
        CheckConstraint("Balance >= 0", name="balance_non_negative"),
    )
