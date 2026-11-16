"""SQLAlchemy 2.x (AsyncSession) implementation of IUnitOfWork.

See Data/Interfaces/i_unit_of_work.py for how a unit of work is used.
"""
from __future__ import annotations

from types import TracebackType
from typing import Any, TypeVar, cast

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, UOWTransaction

from Data.Implementations.repository import DEFAULT_BATCH_SIZE, LoadedState, Repository, RepositoryContext
from Data.Interfaces.i_repository import IRepository, TEntity
from Data.Interfaces.i_unit_of_work import IUnitOfWork, SaveChangesResult
from Data.database_orm_async import Database
from Models.Entities import (Account, AccountType, Customer, Role, Staff, Transaction, TransactionMode,
                             TransactionStatus, TransactionType, User)
from Models.Entities.base_entity import BaseEntity

TUnitOfWork = TypeVar("TUnitOfWork", bound="UnitOfWork")


class UnitOfWork(IUnitOfWork):
    """One AsyncSession, the repositories that work on it, and the changes staged through them."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None, *,
                 batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        """``session_factory`` defaults to the application's async session factory (Data/database_orm_async).
        ``batch_size`` is the number of rows bulk operations load, write or delete per round trip."""
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self._session_factory = session_factory if session_factory is not None else Database().SessionLocal
        self._batch_size = batch_size
        self._context: RepositoryContext | None = None
        self._repositories: dict[type[BaseEntity], Repository[Any]] = {}

    # ------------------------------------------------------------------------------------------------------
    # Lifetime
    # ------------------------------------------------------------------------------------------------------

    async def __aenter__(self: TUnitOfWork) -> TUnitOfWork:
        if self._context is not None:
            raise RuntimeError("this unit of work is already active; use a new UnitOfWork for a nested operation")
        session = self._session_factory()
        # Staged changes reach the database only in save_changes_async(); queries must not flush them early.
        session.sync_session.autoflush = False
        # _async operations commit on this session; entities must stay loaded after those commits.
        session.sync_session.expire_on_commit = False
        self._context = RepositoryContext(session, self._batch_size)
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                        traceback: TracebackType | None) -> None:
        context, self._context = self._context, None
        self._repositories.clear()
        if context is None:
            return
        session = context.close()  # repositories of this unit of work stop working; staged work is dropped
        if session is None:
            return
        try:
            if exc_type is not None:
                loaded = LoadedState(session)
                await session.rollback()
                loaded.restore(session)
        finally:
            await _dispose_session_async(session)

    @property
    def is_active(self) -> bool:
        return self._context is not None

    # ------------------------------------------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------------------------------------------

    def get_repository(self, model: type[TEntity]) -> IRepository[TEntity]:
        context = self._active_context()
        repository = self._repositories.get(model)
        if repository is None:
            repository = Repository(model, context)
            self._repositories[model] = repository
        return cast(IRepository[TEntity], repository)

    @property
    def roles(self) -> IRepository[Role]:
        return self.get_repository(Role)

    @property
    def users(self) -> IRepository[User]:
        return self.get_repository(User)

    @property
    def staff(self) -> IRepository[Staff]:
        return self.get_repository(Staff)

    @property
    def customers(self) -> IRepository[Customer]:
        return self.get_repository(Customer)

    @property
    def account_types(self) -> IRepository[AccountType]:
        return self.get_repository(AccountType)

    @property
    def accounts(self) -> IRepository[Account]:
        return self.get_repository(Account)

    @property
    def transaction_types(self) -> IRepository[TransactionType]:
        return self.get_repository(TransactionType)

    @property
    def transaction_modes(self) -> IRepository[TransactionMode]:
        return self.get_repository(TransactionMode)

    @property
    def transaction_statuses(self) -> IRepository[TransactionStatus]:
        return self.get_repository(TransactionStatus)

    @property
    def transactions(self) -> IRepository[Transaction]:
        return self.get_repository(Transaction)

    # ------------------------------------------------------------------------------------------------------
    # Persisting staged changes
    # ------------------------------------------------------------------------------------------------------

    async def save_changes_async(self) -> SaveChangesResult:
        context = self._active_context()
        session = context.session
        loaded = LoadedState(session)  # taken before anything is written, for a rollback
        counter = _FlushCounter(session)
        try:
            not_found = await context.pending_work.apply_async(session)
            await session.commit()
        except BaseException:
            context.pending_work.clear()
            await session.rollback()
            loaded.restore(session)
            raise
        finally:
            counter.close()
        return SaveChangesResult(added=counter.added, updated=counter.updated, deleted=counter.deleted,
                                 not_found=not_found)

    async def rollback_async(self) -> None:
        context = self._active_context()
        session = context.session
        loaded = LoadedState(session)
        context.pending_work.clear()
        await session.rollback()
        loaded.restore(session)

    # ------------------------------------------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------------------------------------------

    def _active_context(self) -> RepositoryContext:
        if self._context is None:
            raise RuntimeError("the unit of work is not active; use it inside 'async with UnitOfWork() as ...'")
        return self._context


class _FlushCounter:
    """Counts the rows each flush of a session inserts, updates and deletes, while it is listening."""

    def __init__(self, session: AsyncSession) -> None:
        self.added = 0
        self.updated = 0
        self.deleted = 0
        self._session = session.sync_session
        self._listener = self._after_flush  # one bound method object, so it can be removed again
        event.listen(self._session, "after_flush", self._listener)

    def _after_flush(self, session: Session, flush_context: UOWTransaction) -> None:
        # In after_flush the session still shows what this flush wrote as new / dirty / deleted.
        self.added += len(session.new)
        self.deleted += len(session.deleted)
        self.updated += sum(1 for entity in session.dirty if session.is_modified(entity, include_collections=False))

    def close(self) -> None:
        if event.contains(self._session, "after_flush", self._listener):
            event.remove(self._session, "after_flush", self._listener)


async def _dispose_session_async(session: AsyncSession) -> None:
    """Close the session, giving its connection back to the pool. If closing fails (e.g. a broken connection),
    the connection is invalidated instead of being returned to the pool."""
    try:
        await session.close()
    except BaseException:
        await session.invalidate()
        raise
