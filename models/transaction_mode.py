from sqlalchemy import Column, Integer, String, TIMESTAMP, text

from database_orm import Base


class TransactionMode(Base):
    __tablename__ = "TransactionModes"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Name = Column(String(50), unique=True, nullable=False)
