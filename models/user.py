from sqlalchemy.orm import relationship

from database_orm import Base
from sqlalchemy import Column, Integer, String, ForeignKey


class User(Base):
    __tablename__ = "Users"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    LastName = Column(String(100), nullable=False)
    FirstName = Column(String(100), nullable=False)
    Email = Column(String(255), unique=True, nullable=False)
    RoleId = Column(Integer, ForeignKey("Roles.Id"), nullable=False)
    Password = Column(String(255), nullable=False)

    Role = relationship("Role", back_populates="Users")
    Staff = relationship("Staff", uselist=False, back_populates="User")
