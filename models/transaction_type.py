from sqlalchemy import Column, Integer, String, TIMESTAMP, text

from database_orm import Base


class TransactionType(Base):
    __tablename__ = "TransactionTypes"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Name = Column(String(50), unique=True, nullable=False)
