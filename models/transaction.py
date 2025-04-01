from sqlalchemy import Column, Integer, ForeignKey, DECIMAL, TIMESTAMP, String, text
from sqlalchemy.orm import relationship

from database_orm import Base


class Transaction(Base):
    __tablename__ = "Transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("Customers.id"), nullable=False)
    account_type_id = Column(Integer, nullable=True)
    account_number = Column(String(10), nullable=True)
    transaction_type_id = Column(Integer, ForeignKey("TransactionTypes.id"), nullable=False)
    transaction_mode_id = Column(Integer, ForeignKey("TransactionModes.id"), nullable=False)
    transaction_status_id = Column(Integer, ForeignKey("TransactionStatuses.id"), nullable=False)
    amount = Column(DECIMAL(10, 2), nullable=False)
    transaction_date = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    description = Column(String(255), nullable=True)

    customer = relationship("Customer")
    transaction_type = relationship("TransactionType")
    transaction_mode = relationship("TransactionMode")
    transaction_status = relationship("TransactionStatus")
