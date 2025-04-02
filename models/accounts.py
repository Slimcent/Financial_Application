from sqlalchemy.orm import relationship
from models.base_entity import BaseEntity
from sqlalchemy import UniqueConstraint, Column, Integer, ForeignKey, String, DECIMAL


class Account(BaseEntity):
    __tablename__ = "Accounts"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    CustomerId = Column(Integer, ForeignKey("Customers.Id"), nullable=False)
    AccountTypeId = Column(Integer, ForeignKey("AccountTypes.Id"), nullable=False)
    AccountNumber = Column(String(10), unique=True, nullable=False)
    Balance = Column(DECIMAL(10, 2), default=0.00, nullable=False)

    customer = relationship("Customer", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")

    __table_args__ = (UniqueConstraint("CustomerId", "AccountTypeId", name="uq_customer_account_type"),)
