from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from Models.Entities.base_entity import LAZY, BaseEntity

if TYPE_CHECKING:
    from Models.Entities.accounts import Account


class AccountType(BaseEntity):
    __tablename__ = "AccountTypes"

    Id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    Type: Mapped[str] = mapped_column(String(50), unique=True)

    # An account type in use cannot be deleted (Accounts.AccountTypeId is ON DELETE RESTRICT).
    accounts: Mapped[list["Account"]] = relationship(back_populates="account_type", lazy=LAZY,
                                                     passive_deletes="all")
