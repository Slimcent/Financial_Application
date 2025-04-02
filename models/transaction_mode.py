from models.base_entity import BaseEntity
from sqlalchemy import Column, Integer, String


class TransactionMode(BaseEntity):
    __tablename__ = "TransactionModes"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Name = Column(String(50), unique=True, nullable=False)
