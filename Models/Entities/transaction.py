import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (DECIMAL, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from Models.Entities.base_entity import LAZY, BaseEntity
from Models.Entities.column_types import GUID, UTC_NOW_SERVER_DEFAULT, UtcDateTime, utc_now, uuid7

if TYPE_CHECKING:
    from Models.Entities.accounts import Account
    from Models.Entities.transaction_mode import TransactionMode
    from Models.Entities.transaction_status import TransactionStatus
    from Models.Entities.transaction_type import TransactionType
    from Models.Entities.user import User


class Transaction(BaseEntity):
    __tablename__ = "Transactions"

    Id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid7)
    # Together with UserId, a foreign key to Accounts (Id, UserId): see __table_args__.
    AccountId: Mapped[uuid.UUID] = mapped_column(GUID)
    TransactionTypeId: Mapped[int] = mapped_column(Integer, ForeignKey("TransactionTypes.Id", ondelete="RESTRICT"),
                                                   index=True)
    TransactionModeId: Mapped[int] = mapped_column(Integer, ForeignKey("TransactionModes.Id", ondelete="RESTRICT"),
                                                   index=True)
    TransactionStatusId: Mapped[int] = mapped_column(Integer,
                                                     ForeignKey("TransactionStatuses.Id", ondelete="RESTRICT"),
                                                     index=True)
    Amount: Mapped[Decimal] = mapped_column(DECIMAL(10, 2))
    # When the transaction took place (UTC). Unless set explicitly it is the same instant as CreatedAt
    # (the time the row was recorded); indexed for date ordering.
    TransactionDate: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now,
                                                      server_default=UTC_NOW_SERVER_DEFAULT, index=True)
    Description: Mapped[str | None] = mapped_column(String(255))
    # The owner of the account (enforced by the composite foreign key below).
    UserId: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("Users.Id", ondelete="RESTRICT"), index=True)
    # The user who sent the money, if any.
    SenderId: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("Users.Id", ondelete="RESTRICT"), index=True)
    # Shared by the debit and the credit row of one transfer; NULL for transactions that are not transfers.
    TransferReference: Mapped[uuid.UUID | None] = mapped_column(GUID)

    account: Mapped["Account"] = relationship(back_populates="transactions", lazy=LAZY,
                                              primaryjoin="Transaction.AccountId == Account.Id",
                                              foreign_keys=[AccountId])
    transaction_type: Mapped["TransactionType"] = relationship(lazy=LAZY)
    transaction_mode: Mapped["TransactionMode"] = relationship(lazy=LAZY)
    transaction_status: Mapped["TransactionStatus"] = relationship(lazy=LAZY)
    user: Mapped["User"] = relationship(back_populates="transactions", lazy=LAZY, foreign_keys=[UserId])
    sender: Mapped[Optional["User"]] = relationship(back_populates="sent_transactions", lazy=LAZY,
                                                    foreign_keys=[SenderId])

    __table_args__ = (
        # The account must exist and belong to UserId.
        ForeignKeyConstraint(["AccountId", "UserId"], ["Accounts.Id", "Accounts.UserId"], ondelete="RESTRICT"),
        Index(None, "AccountId", "UserId"),
        # A transfer has at most one debit and one credit row.
        UniqueConstraint("TransferReference", "TransactionModeId"),
        CheckConstraint("Amount > 0", name="amount_positive"),
    )

    def _apply_insert_timestamps(self, now: datetime) -> None:
        super()._apply_insert_timestamps(now)
        if self.TransactionDate is None:
            self.TransactionDate = self.CreatedAt
