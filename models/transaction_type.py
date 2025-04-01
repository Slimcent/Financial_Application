from sqlalchemy import Column, Integer, String, TIMESTAMP, text

from database_orm import Base


class TransactionType(Base):
    __tablename__ = "TransactionTypes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
