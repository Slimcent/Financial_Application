from sqlalchemy.orm import relationship
from models.base_entity import BaseEntity
from sqlalchemy import Column, Integer, ForeignKey, DECIMAL, TIMESTAMP, String, text


class Transaction(BaseEntity):
    __tablename__ = "Transactions"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    AccountId = Column(Integer, ForeignKey("Accounts.Id"), nullable=False)
    TransactionTypeId = Column(Integer, ForeignKey("TransactionTypes.Id"), nullable=False)
    TransactionModeId = Column(Integer, ForeignKey("TransactionModes.Id"), nullable=False)
    TransactionStatusId = Column(Integer, ForeignKey("TransactionStatuses.Id"), nullable=False)
    Amount = Column(DECIMAL(10, 2), nullable=False)
    TransactionDate = Column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
    Description = Column(String(255), nullable=True)
    UserId = Column(Integer, ForeignKey("Users.Id"), nullable=False)

    account = relationship("Account", back_populates="transactions")
    transaction_type = relationship("TransactionType")
    transaction_mode = relationship("TransactionMode")
    transaction_status = relationship("TransactionStatus")
    user = relationship("User")
