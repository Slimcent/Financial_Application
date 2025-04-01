from sqlalchemy import Column, Integer, ForeignKey, DECIMAL, TIMESTAMP, String, text
from sqlalchemy.orm import relationship

from database_orm import Base


class Transaction(Base):
    __tablename__ = "Transactions"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    CustomerId = Column(Integer, ForeignKey("Customers.Id"), nullable=False)
    AccountTypeId = Column(Integer, nullable=True)
    Account_Number = Column(String(10), nullable=True)
    TransactionTypeId = Column(Integer, ForeignKey("TransactionTypes.Id"), nullable=False)
    TransactionModeId = Column(Integer, ForeignKey("TransactionModes.Id"), nullable=False)
    TransactionStatusId = Column(Integer, ForeignKey("TransactionStatuses.Id"), nullable=False)
    Amount = Column(DECIMAL(10, 2), nullable=False)
    TransactionDate = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    Description = Column(String(255), nullable=True)

    customer = relationship("Customer")
    transaction_type = relationship("TransactionType")
    transaction_mode = relationship("TransactionMode")
    transaction_status = relationship("TransactionStatus")
