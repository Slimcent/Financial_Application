from database_orm import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, ForeignKey, DECIMAL


class Customer(Base):
    __tablename__ = "Customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False, unique=True)
    account_type_id = Column(Integer, nullable=True)
    balance = Column(DECIMAL(10, 2), nullable=False, default=0.00)

    user = relationship("User")
