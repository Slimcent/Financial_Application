from models.base_entity import BaseEntity
from sqlalchemy import Integer, Column, String


class TransactionStatus(BaseEntity):
    __tablename__ = "TransactionStatuses"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Name = Column(String(50), unique=True, nullable=False)
