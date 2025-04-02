from database_orm import Base
from models.base_entity import BaseEntity
from sqlalchemy import Column, Integer, String


class AccountType(BaseEntity):
    __tablename__ = "AccountTypes"

    Id = Column(Integer, primary_key=True, autoincrement=True)
    Type = Column(String(50), unique=True, nullable=False)
