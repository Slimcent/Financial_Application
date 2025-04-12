from sqlalchemy.orm import relationship

from database_orm import Base
from models.base_entity import BaseEntity
from sqlalchemy import Column, Integer, ForeignKey, String


class Customer(BaseEntity):
    __tablename__ = "Customers"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    UserId = Column(Integer, ForeignKey("Users.Id"), nullable=False)
    Address = Column(String(255), nullable=True)

    accounts = relationship("Account", back_populates="customer")
    Customer = relationship("Customer", uselist=False, back_populates="User")
