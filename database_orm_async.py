# import os
# from dotenv import load_dotenv
# from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
# from sqlalchemy.orm import declarative_base
#
# # Load environment variables
# load_dotenv()
# print(".env loaded")
#
# # Async Database connection URL
# DATABASE_URL = f"mysql+aiomysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@" \
#                f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
#
# # Create async SQLAlchemy engine (no await needed here)
# engine = create_async_engine(DATABASE_URL, echo=True)
#
# # Base for models
# Base = declarative_base()
#
# # Use async_sessionmaker here instead of sessionmaker
# AsyncSessionLocal = async_sessionmaker(
#     bind=engine,
#     class_=AsyncSession,
#     expire_on_commit=False,
# )


import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import (create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine)


# class Database:
#     def __init__(self):
#
#         load_dotenv()
#         print(".env loaded")
#
#         self.database_url = _build_database_url()
#         self.engine: AsyncEngine = self._create_engine()
#         self.SessionLocal = self._create_session_maker()
#         self.Base = declarative_base()
#
#     def _create_engine(self) -> AsyncEngine:
#         return create_async_engine(self.database_url, echo=True)
#
#     def _create_session_maker(self):
#         return async_sessionmaker(
#             bind=self.engine,
#             class_=AsyncSession,
#             expire_on_commit=False
#         )
#
#     @asynccontextmanager
#     async def get_session(self):
#         async with self.SessionLocal() as session:
#             try:
#                 yield session
#             finally:
#                 await session.close()
#
#     async def dispose(self):
#         if self.engine:
#             await self.engine.dispose()
#             print("Database engine disposed.")
#
#
# def _build_database_url() -> str:
#     return (
#         f"mysql+aiomysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
#         f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
#     )

class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        load_dotenv()
        print(".env loaded")

        self.database_url = _build_database_url()
        self.engine: AsyncEngine = self._create_engine()
        self.SessionLocal = self._create_session_maker()
        self.Base = declarative_base()

    def _create_engine(self) -> AsyncEngine:
        return create_async_engine(self.database_url, echo=True)

    def _create_session_maker(self):
        return async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    @asynccontextmanager
    async def get_session(self):
        async with self.SessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    async def dispose(self):
        if self.engine:
            await self.engine.dispose()
            print("Database engine disposed.")


def _build_database_url() -> str:
    return (
        f"mysql+aiomysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )

