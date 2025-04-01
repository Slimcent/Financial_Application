from database_orm import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, ForeignKey, DECIMAL, String, UniqueConstraint


class Customer(Base):
    __tablename__ = "Customers"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    UserId = Column(Integer, ForeignKey("Users.Id"), nullable=False)
    AccountTypeId = Column(Integer, ForeignKey("AccountTypes.Id"), nullable=False)
    AccountNumber = Column(String(10), unique=True, nullable=False)
    Balance = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    Address = Column(String(255), nullable=True)

    transactions = relationship("Transaction", back_populates="customer")
    user = relationship("User")
    account_type = relationship("AccountType")

    __table_args__ = (UniqueConstraint("UserId", "AccountTypeId", name="uq_user_accounttype"),)