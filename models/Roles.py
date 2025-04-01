from sqlalchemy.orm import relationship

from database_orm import Base
from sqlalchemy import Column, Integer, String


class Role(Base):
    __tablename__ = "Roles"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Name = Column(String(100), unique=True, nullable=False)

    Users = relationship("User", back_populates="Role")
