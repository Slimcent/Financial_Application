from models.base_entity import BaseEntity
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey


class Staff(BaseEntity):
    __tablename__ = "Staff"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    UserId = Column(Integer, ForeignKey("Users.Id"), nullable=False, unique=True)
    Position = Column(String(100), nullable=False)

    User = relationship("User", back_populates="Staff")
