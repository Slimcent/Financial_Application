from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from Models.Entities.base_entity import BaseEntity


class TransactionType(BaseEntity):
    __tablename__ = "TransactionTypes"

    Id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    Name: Mapped[str] = mapped_column(String(50), unique=True)
