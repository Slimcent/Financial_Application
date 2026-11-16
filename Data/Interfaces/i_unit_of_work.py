"""Contract of the unit of work: one session shared by the repositories of one business operation, which
collects staged (non-persisting) changes and persists them all at once.

Usage::

    async with UnitOfWork() as unit_of_work:
        account = await unit_of_work.accounts.get_single_async(Account.AccountNumber == account_number)
        unit_of_work.accounts.update_single(account, {"Balance": account.Balance + amount})
        unit_of_work.transactions.add_single(Transaction(...))
        result = await unit_of_work.save_changes_async()   # the balance and the transaction row, one commit

* Operations without the ``_async`` suffix (add / update / delete / save) only stage changes;
  ``save_changes_async()`` persists everything staged, in one transaction and in call order.
* Repository ``_async`` operations (add / update / delete / save) persist their own data at once, on this
  unit of work's session but in a transaction of their own: the staged changes are set aside while they run
  and stay staged. They end this unit of work's current database transaction (which only holds reads), so
  row locks taken with ``for_update`` are released.
* Queries run on this unit of work's session and do not flush staged changes.
* Leaving the ``async with`` block without ``save_changes_async()`` discards everything staged. An exception
  inside the block rolls back. Either way the session is closed and disposed of when the block ends, and the
  repositories of this unit of work stop working. A unit of work is not shared between concurrent tasks.
* After a rollback (``rollback_async()``, a failed save, or an exception in the block) the entities keep the
  values they were loaded with, so they can still be read.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any, TypeAlias, TypeVar

from Data.Interfaces.i_repository import IRepository, TEntity
from Models.Entities import (Account, AccountType, Customer, Role, Staff, Transaction, TransactionMode,
                             TransactionStatus, TransactionType, User)

TUnitOfWork = TypeVar("TUnitOfWork", bound="IUnitOfWork")


@dataclass(frozen=True)
class SaveChangesResult:
    """What save_changes_async() wrote."""

    added: int = 0
    updated: int = 0
    deleted: int = 0
    # (entity name, primary key) of rows that delete_by_id() was asked to delete but that did not exist.
    not_found: tuple[tuple[str, Any], ...] = ()

    @property
    def total(self) -> int:
        """The number of rows added, updated and deleted."""
        return self.added + self.updated + self.deleted


class IUnitOfWork(ABC):
    """One session, the repositories that work on it, and the changes staged through them."""

    # ------------------------------------------------------------------------------------------------------
    # Lifetime
    # ------------------------------------------------------------------------------------------------------

    @abstractmethod
    async def __aenter__(self: TUnitOfWork) -> TUnitOfWork:
        """Open the session."""

    @abstractmethod
    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                        traceback: TracebackType | None) -> None:
        """Roll back if the block raised, then close and dispose of the session (unsaved staged changes are
        discarded); the repositories of this unit of work stop working."""

    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Whether the unit of work is open (inside its ``async with`` block)."""

    # ------------------------------------------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------------------------------------------

    @abstractmethod
    def get_repository(self, model: type[TEntity]) -> IRepository[TEntity]:
        """The repository of an entity type in this unit of work (one instance per type)."""

    @property
    @abstractmethod
    def roles(self) -> IRepository[Role]: ...

    @property
    @abstractmethod
    def users(self) -> IRepository[User]: ...

    @property
    @abstractmethod
    def staff(self) -> IRepository[Staff]: ...

    @property
    @abstractmethod
    def customers(self) -> IRepository[Customer]: ...

    @property
    @abstractmethod
    def account_types(self) -> IRepository[AccountType]: ...

    @property
    @abstractmethod
    def accounts(self) -> IRepository[Account]: ...

    @property
    @abstractmethod
    def transaction_types(self) -> IRepository[TransactionType]: ...

    @property
    @abstractmethod
    def transaction_modes(self) -> IRepository[TransactionMode]: ...

    @property
    @abstractmethod
    def transaction_statuses(self) -> IRepository[TransactionStatus]: ...

    @property
    @abstractmethod
    def transactions(self) -> IRepository[Transaction]: ...

    # ------------------------------------------------------------------------------------------------------
    # Persisting staged changes
    # ------------------------------------------------------------------------------------------------------

    @abstractmethod
    async def save_changes_async(self) -> SaveChangesResult:
        """Persist every change staged through this unit of work's repositories, in one transaction and in the
        order the operations were called. Returns what was written.

        On failure nothing is persisted: the transaction is rolled back, the staged changes are discarded (the
        entities keep the values they were loaded with) and the error is re-raised.
        """

    @abstractmethod
    async def rollback_async(self) -> None:
        """Discard every staged change and end the current transaction (releasing any row locks); the entities
        keep the values they were loaded with."""


# Creates a new, not yet active unit of work. The caller enters it (``async with factory() as unit_of_work``), passes
# it to the services it calls and so decides where a business operation starts and ends.
UnitOfWorkFactory: TypeAlias = Callable[[], IUnitOfWork]
