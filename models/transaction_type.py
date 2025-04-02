from models.base_entity import BaseEntity
from sqlalchemy import Column, Integer, String


class TransactionType(BaseEntity):
    __tablename__ = "TransactionTypes"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Name = Column(String(50), unique=True, nullable=False)
