from sqlalchemy.orm import declarative_base

from database_orm import Base
from sqlalchemy import Column, DateTime, func


class BaseEntity(Base):
    __abstract__ = True

    CreatedAt = Column(DateTime, default=func.now(), nullable=False)
    UpdatedAt = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
