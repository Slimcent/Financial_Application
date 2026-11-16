"""Fixtures for the unit of work tests: sessions that record what the unit of work does with them.

The database fixtures (engine, session_factory, bank, persisted, ...) come from tests/unit/Data/conftest.py.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class RecordingSession(AsyncSession):
    """An AsyncSession that records the commit / rollback / close / invalidate calls made on it."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

    async def commit(self):
        self.calls.append("commit")
        await super().commit()

    async def rollback(self):
        self.calls.append("rollback")
        await super().rollback()

    async def close(self):
        self.calls.append("close")
        await super().close()

    async def invalidate(self):
        self.calls.append("invalidate")
        await super().invalidate()


class ClosingFailsSession(RecordingSession):
    """A session whose connection breaks while it is being closed."""

    async def close(self):
        self.calls.append("close")
        raise ConnectionError("connection lost while closing")


class RecordingSessionFactory:
    """A session factory (like async_sessionmaker) that keeps every session it creates."""

    def __init__(self, engine, session_class):
        self._factory = async_sessionmaker(bind=engine, class_=session_class, expire_on_commit=False)
        self.sessions = []

    def __call__(self, **kwargs):
        session = self._factory(**kwargs)
        self.sessions.append(session)
        return session


@pytest.fixture
def recording_factory(engine):
    return RecordingSessionFactory(engine, RecordingSession)


@pytest.fixture
def closing_fails_factory(engine):
    return RecordingSessionFactory(engine, ClosingFailsSession)
