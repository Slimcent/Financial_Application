from database_orm import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, ForeignKey, DECIMAL


class Customer(Base):
    __tablename__ = "Customers"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    UserId = Column(Integer, ForeignKey("Users.Id"), nullable=False, unique=True)
    AccountTypeid = Column(Integer, nullable=True)
    Balance = Column(DECIMAL(10, 2), nullable=False, default=0.00)

    user = relationship("User")
