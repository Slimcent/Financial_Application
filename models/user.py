from sqlalchemy.dialects.mysql import TIMESTAMP
from sqlalchemy.orm import relationship
from models.base_entity import BaseEntity
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, func


class User(BaseEntity):
    __tablename__ = "Users"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    LastName = Column(String(100), nullable=False)
    FirstName = Column(String(100), nullable=False)
    Email = Column(String(255), unique=True, nullable=False)
    RoleId = Column(Integer, ForeignKey("Roles.Id"), nullable=False)
    Password = Column(String(255), nullable=False)
    Active = Column(Boolean, nullable=False, server_default="1")
    CreatedAt = Column(TIMESTAMP, nullable=False, server_default=func.now())
    UpdatedAt = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

    Role = relationship("Role", back_populates="Users")
    Staff = relationship("Staff", uselist=False, back_populates="User")
