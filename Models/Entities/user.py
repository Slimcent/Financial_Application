import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from Models.Entities.base_entity import LAZY, BaseEntity
from Models.Entities.column_types import GUID, uuid7

if TYPE_CHECKING:
    from Models.Entities.Roles import Role
    from Models.Entities.Staff import Staff
    from Models.Entities.accounts import Account
    from Models.Entities.customer import Customer
    from Models.Entities.transaction import Transaction


class User(BaseEntity):
    __tablename__ = "Users"

    Id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid7)
    LastName: Mapped[str] = mapped_column(String(100))
    FirstName: Mapped[str] = mapped_column(String(100))
    Email: Mapped[str] = mapped_column(String(255), unique=True)
    RoleId: Mapped[int] = mapped_column(Integer, ForeignKey("Roles.Id", ondelete="RESTRICT"), index=True)
    Password: Mapped[str] = mapped_column(String(255))
    Active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    Role: Mapped["Role"] = relationship(back_populates="Users", lazy=LAZY)

    # A user cannot be deleted while it still has a staff/customer record, accounts or transactions
    # (all of those foreign keys are ON DELETE RESTRICT); the ORM leaves that check to the database.
    Staff: Mapped[Optional["Staff"]] = relationship(back_populates="User", lazy=LAZY, passive_deletes="all")
    customer: Mapped[Optional["Customer"]] = relationship(back_populates="user", lazy=LAZY, passive_deletes="all")
    accounts: Mapped[list["Account"]] = relationship(back_populates="user", lazy=LAZY, passive_deletes="all")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", lazy=LAZY,
                                                             passive_deletes="all",
                                                             foreign_keys="Transaction.UserId")
    sent_transactions: Mapped[list["Transaction"]] = relationship(back_populates="sender", lazy=LAZY,
                                                                  passive_deletes="all",
                                                                  foreign_keys="Transaction.SenderId")
