from sqlalchemy.orm import relationship
from models.base_entity import BaseEntity
from sqlalchemy import UniqueConstraint, Column, Integer, ForeignKey, String, DECIMAL


class Account(BaseEntity):
    __tablename__ = "Accounts"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    UserId = Column(Integer, ForeignKey("Users.Id"), nullable=False)
    AccountTypeId = Column(Integer, ForeignKey("AccountTypes.Id"), nullable=False)
    AccountNumber = Column(String(10), unique=True, nullable=False)
    Balance = Column(DECIMAL(10, 2), default=0.00, nullable=False)

    user = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")
    account_type = relationship("AccountType", back_populates="accounts")

    __table_args__ = (
        UniqueConstraint("UserId", "AccountTypeId", name="uq_user_account_type"),
    )

