import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from Models.Entities.base_entity import LAZY, BaseEntity
from Models.Entities.column_types import GUID, uuid7

if TYPE_CHECKING:
    from Models.Entities.user import User


class Customer(BaseEntity):
    __tablename__ = "Customers"

    Id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid7)
    UserId: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("Users.Id", ondelete="RESTRICT"),
                                              unique=True)  # one customer record per user
    Address: Mapped[str | None] = mapped_column(String(255))

    user: Mapped["User"] = relationship(back_populates="customer", lazy=LAZY)
