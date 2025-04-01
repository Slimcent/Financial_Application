from sqlalchemy import Integer, Column, String, text, TIMESTAMP

from database_orm import Base


class TransactionStatus(Base):
    __tablename__ = "TransactionStatuses"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Name = Column(String(50), unique=True, nullable=False)
