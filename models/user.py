from database_orm import Base
from sqlalchemy import Column, Integer, String


class User(Base):
    __tablename__ = "Users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    last_name = Column(String(100), nullable=False)
    first_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role_id = Column(Integer, nullable=False)
    password = Column(String(255), nullable=False)
