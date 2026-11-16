from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from Models.Entities.base_entity import LAZY, BaseEntity

if TYPE_CHECKING:
    from Models.Entities.user import User


class Role(BaseEntity):
    __tablename__ = "Roles"

    Id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    Name: Mapped[str] = mapped_column(String(100), unique=True)

    # A role in use cannot be deleted (Users.RoleId is ON DELETE RESTRICT).
    Users: Mapped[list["User"]] = relationship(back_populates="Role", lazy=LAZY, passive_deletes="all")
