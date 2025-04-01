from database_orm import Base
from sqlalchemy import Column, Integer, String


class AccountType(Base):
    __tablename__ = "AccountTypes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(50), unique=True, nullable=False)
