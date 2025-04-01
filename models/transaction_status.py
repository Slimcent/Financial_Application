from sqlalchemy import Integer, Column, String, text, TIMESTAMP

from database_orm import Base


class TransactionStatus(Base):
    __tablename__ = "TransactionStatuses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))