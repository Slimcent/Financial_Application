from database_orm import Base
from sqlalchemy import Column, Integer, String, ForeignKey


class Staff(Base):
    __tablename__ = "Staff"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    UserId = Column(Integer, ForeignKey("Users.id"), nullable=False)
    Position = Column(String(100), nullable=False)
