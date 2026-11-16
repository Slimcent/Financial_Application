"""Contract of the repository: the single gateway to the database for every entity.

Naming convention
-----------------
* Operation groups: ``add``, ``update``, ``delete``, ``get`` and ``save`` (plus the ``count`` / ``sum`` /
  ``exists`` queries).
* ``_single`` works on one entity, ``_range`` on many (bulk).
* Only methods ending in ``_async`` are awaited; every other method is a plain call.
* No suffix: NOT persisted. The change is staged in the unit of work and written, together with every other
  staged change and in the order the operations were called, when ``IUnitOfWork.save_changes_async()`` runs.
* ``_async`` suffix on add / update / delete / save: persisted at once. The operation runs on the unit of
  work's own session (so it never waits on row locks the unit of work holds) in a transaction of its own:
  changes staged in the unit of work are set aside while it runs and kept, staged, afterwards. Only the data
  of that call is committed. Committing ends the unit of work's current database transaction, which only
  holds reads (staged changes are never written before ``save_changes_async()``): row locks taken with
  ``for_update`` are released and later queries see the latest committed data.
* ``_async`` suffix on queries (``get_*``, ``count``, ``sum``, ``exists``): the query runs on the unit of
  work's session. Queries do not flush staged changes, so they see the database as it is.

Every add / update / delete goes through the ORM, one entity at a time, so mapper events, defaults and
``onupdate`` values apply to bulk operations too. Bulk operations by criteria work through the matching rows
in primary-key batches, so they never hold every matching row in memory at once.

Entities the unit of work tracks stay usable after a rollback: they keep the values they were loaded with.

Criteria, includes and ordering
-------------------------------
* Criteria are SQLAlchemy boolean expressions on the entity, e.g. ``Account.AccountNumber == "2606387058"``.
  Conditions on related tables are written with ``has()`` / ``any()``, e.g.
  ``Transaction.account.has(Account.AccountTypeId == 1)`` or ``User.accounts.any(Account.Balance > 0)``.
* Queries that criteria cannot express are built from ``query()`` and passed in as a statement.
* Includes load related objects in the same operation (relationships never load implicitly: they are
  ``raise_on_sql``). An include is one of:
    - a relationship path string, e.g. ``"account_type"`` or ``"user.customer"``;
    - a relationship attribute, e.g. ``Account.user``;
    - a path of relationship attributes, e.g. ``(Account.user, User.customer)``;
    - a ready-made loader option, e.g. ``selectinload(User.accounts).joinedload(Account.account_type)``.
  Collections are loaded with ``selectinload`` and single objects with ``joinedload``.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import Any, Generic, TypeAlias, TypeVar, Union, overload

from sqlalchemy import ColumnElement, Select
from sqlalchemy.orm import QueryableAttribute
from sqlalchemy.orm.interfaces import LoaderOption

from Models.Dtos.Response.paged_response import PagedResponse
from Models.Entities.base_entity import BaseEntity

TEntity = TypeVar("TEntity", bound=BaseEntity)

# Primary key of an entity: GUID for the main entities, integer for the lookup entities.
EntityId: TypeAlias = Union[uuid.UUID, int]

# A boolean SQL condition on the entity, e.g. Account.Balance > 0.
Criterion: TypeAlias = ColumnElement[bool]

# Related objects to load with the result (see the module documentation).
Include: TypeAlias = Union[str, QueryableAttribute[Any], Sequence[QueryableAttribute[Any]], LoaderOption]

# An ordering term, e.g. Transaction.TransactionDate.desc() or Account.AccountNumber.
OrderBy: TypeAlias = Union[ColumnElement[Any], QueryableAttribute[Any]]

# Attribute name -> new value. A value may be an SQL expression, e.g. {"Balance": Account.Balance + amount}.
Values: TypeAlias = Mapping[str, Any]

# Result of sum_async(): Decimal for DECIMAL columns (money), int / float for other numeric columns.
Number: TypeAlias = Union[Decimal, int, float]


class IRepository(ABC, Generic[TEntity]):
    """CRUD operations and queries for one entity type, within a unit of work.

    A repository belongs to the unit of work that created it and stops working when that unit of work ends.
    """

    @property
    @abstractmethod
    def model(self) -> type[TEntity]:
        """The entity class this repository works on."""

    # ------------------------------------------------------------------------------------------------------
    # Query building
    # ------------------------------------------------------------------------------------------------------

    @abstractmethod
    def query(self) -> Select[Any]:
        """A new ``SELECT`` of the entity, to extend (joins, filters, ordering) and pass to a get / count /
        exists operation. Building the statement does not run it."""

    # ------------------------------------------------------------------------------------------------------
    # Get (single)
    # ------------------------------------------------------------------------------------------------------

    @abstractmethod
    async def get_by_id_async(self, entity_id: EntityId, *, includes: Sequence[Include] = (),
                              for_update: bool = False) -> TEntity | None:
        """The entity with this primary key, or None.

        ``for_update`` locks the row (``SELECT ... FOR UPDATE``) until the unit of work's transaction ends.
        An entity the unit of work already tracks gets the locked row's column values; changes staged on it
        are kept on top of them, and its loaded relationships are kept.
        """

    @overload
    async def get_single_async(self, *criteria: Criterion, includes: Sequence[Include] = (),
                               for_update: bool = False) -> TEntity | None: ...

    @overload
    async def get_single_async(self, statement: Select[Any], /, *, includes: Sequence[Include] = (),
                               for_update: bool = False) -> TEntity | None: ...

    @abstractmethod
    async def get_single_async(self, *criteria: Any, includes: Sequence[Include] = (),
                               for_update: bool = False) -> TEntity | None:
        """The one entity that matches the filter (criteria, or a statement with a WHERE clause), or None.

        The filter must identify at most one row: a filter is required, and
        ``sqlalchemy.exc.MultipleResultsFound`` is raised when more than one row matches.
        """

    # ------------------------------------------------------------------------------------------------------
    # Get (range)
    # ------------------------------------------------------------------------------------------------------

    @overload
    async def get_range_async(self, *criteria: Criterion, includes: Sequence[Include] = (),
                              order_by: Sequence[OrderBy] = (), skip: int | None = None, take: int | None = None,
                              for_update: bool = False) -> list[TEntity]: ...

    @overload
    async def get_range_async(self, statement: Select[Any], /, *, includes: Sequence[Include] = (),
                              order_by: Sequence[OrderBy] = (), skip: int | None = None, take: int | None = None,
                              for_update: bool = False) -> list[TEntity]: ...

    @overload
    async def get_range_async(self, *criteria: Criterion, page: int, page_size: int,
                              includes: Sequence[Include] = (), order_by: Sequence[OrderBy] = ()
                              ) -> PagedResponse[TEntity]: ...

    @overload
    async def get_range_async(self, statement: Select[Any], /, *, page: int, page_size: int,
                              includes: Sequence[Include] = (), order_by: Sequence[OrderBy] = ()
                              ) -> PagedResponse[TEntity]: ...

    @abstractmethod
    async def get_range_async(self, *criteria: Any, includes: Sequence[Include] = (),
                              order_by: Sequence[OrderBy] = (), skip: int | None = None, take: int | None = None,
                              for_update: bool = False, page: int | None = None, page_size: int | None = None
                              ) -> list[TEntity] | PagedResponse[TEntity]:
        """All entities that match the criteria (or the statement); no criteria returns every row.

        * ``skip`` / ``take``: offset and limit, returns a list.
        * ``page`` / ``page_size`` (both required, 1-based page): returns a PagedResponse with the total number
          of matching rows. Paging is done by the database; the primary key is added as the last ordering
          term so pages are stable.
        * ``for_update`` locks the returned rows until the transaction ends (not available with paging); see
          get_by_id_async() for entities already tracked.
        """

    # ------------------------------------------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------------------------------------------

    @overload
    async def count_async(self, *criteria: Criterion) -> int: ...

    @overload
    async def count_async(self, statement: Select[Any], /) -> int: ...

    @abstractmethod
    async def count_async(self, *criteria: Any) -> int:
        """The number of rows that match the criteria (or the statement); no criteria counts every row."""

    @overload
    async def sum_async(self, column: QueryableAttribute[Any] | ColumnElement[Any],
                        *criteria: Criterion) -> Number: ...

    @overload
    async def sum_async(self, column: QueryableAttribute[Any] | ColumnElement[Any],
                        statement: Select[Any], /) -> Number: ...

    @abstractmethod
    async def sum_async(self, column: QueryableAttribute[Any] | ColumnElement[Any], *criteria: Any) -> Number:
        """The sum of a numeric column (or expression) over the rows that match the criteria (or the statement);
        no criteria sums over every row, and the result is 0 when no row matches.

        A statement (built from ``query()``) is optional and allows joins, e.g. summing the balances of the
        accounts whose owner is active. Its ordering, offset and limit are ignored, as in count_async().

        Examples: ``await accounts.sum_async(Account.Balance, Account.UserId == user_id)``;
        ``await accounts.sum_async(Account.Balance, accounts.query().join(Account.user).where(User.Active))``.
        """

    @overload
    async def exists_async(self, *criteria: Criterion) -> bool: ...

    @overload
    async def exists_async(self, statement: Select[Any], /) -> bool: ...

    @abstractmethod
    async def exists_async(self, *criteria: Any) -> bool:
        """Whether at least one row matches the criteria (or the statement)."""

    # ------------------------------------------------------------------------------------------------------
    # Add
    # ------------------------------------------------------------------------------------------------------

    @abstractmethod
    def add_single(self, entity: TEntity) -> TEntity:
        """Stage a new entity (not persisted). Key defaults are applied when the unit of work saves.

        New related objects reachable from the entity (e.g. items of its collections) are saved with it.
        """

    @abstractmethod
    async def add_single_async(self, entity: TEntity) -> TEntity:
        """Insert a new entity at once, in its own transaction; returns it with its key and defaults filled in.

        Only the entity's own row is written. A many-to-one related object must already be saved, and related
        objects in its collections are not saved by this call: for an entity that is not staged in the unit of
        work, a non-empty collection is refused. If the entity was staged in the unit of work, it is now tracked
        there as an existing entity and the related objects stay staged.
        """

    @abstractmethod
    def add_range(self, entities: Iterable[TEntity]) -> list[TEntity]:
        """Stage new entities (not persisted)."""

    @abstractmethod
    async def add_range_async(self, entities: Iterable[TEntity]) -> list[TEntity]:
        """Insert new entities at once, in one transaction of their own (all or nothing); see add_single_async()."""

    # ------------------------------------------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------------------------------------------

    @abstractmethod
    def update_single(self, entity: TEntity, values: Values | None = None) -> TEntity:
        """Stage changes to an entity (not persisted) and return the entity the unit of work tracks.

        ``values`` (attribute name -> value) are applied to the entity at once, so it shows them; primary keys
        cannot be changed. An entity loaded through this unit of work is tracked already: changing its
        attributes is enough. A detached entity (loaded elsewhere) is attached; if the unit of work already
        tracks the same row, the detached entity's changes are copied onto the tracked entity, which is
        returned. References to other rows the unit of work already tracks are pointed at the tracked entities.
        """

    @abstractmethod
    async def update_single_async(self, entity: TEntity, values: Values | None = None) -> TEntity:
        """Write an existing entity's changed columns and ``values`` at once, in their own transaction.

        The row is updated through the ORM; only this entity's own row is written (its columns, including the
        foreign keys of changed many-to-one relationships). Changes that live in other rows (collections,
        one-to-one relationships) stay staged when the unit of work tracks the entity, and are refused
        otherwise. The given entity, and the unit of work's copy of the row, get the stored values (changes
        still staged on the unit of work's copy are kept). Returns the given entity.
        """

    @overload
    def update_range(self, entities: Iterable[TEntity], /, *, values: Values | None = None) -> list[TEntity]: ...

    @overload
    def update_range(self, *criteria: Criterion, values: Values) -> None: ...

    @abstractmethod
    def update_range(self, *args: Any, values: Values | None = None) -> list[TEntity] | None:
        """Stage an update of many entities (not persisted).

        * ``update_range(entities, values=None)``: update_single() for each entity; returns the tracked entities.
        * ``update_range(*criteria, values=...)``: when the unit of work saves, the matching rows are loaded in
          batches and ``values`` are applied to each of them through the ORM. At least one criterion is
          required. Values may be SQL expressions, e.g. ``{"Balance": Account.Balance + amount}``.
        """

    @overload
    async def update_range_async(self, entities: Iterable[TEntity], /, *,
                                 values: Values | None = None) -> list[TEntity]: ...

    @overload
    async def update_range_async(self, *criteria: Criterion, values: Values) -> int: ...

    @abstractmethod
    async def update_range_async(self, *args: Any, values: Values | None = None) -> list[TEntity] | int:
        """Update many entities at once, in one transaction of their own (all or nothing).

        * ``update_range_async(entities, values=None)``: update_single_async() for each entity; returns them.
        * ``update_range_async(*criteria, values=...)``: applies ``values`` to the matching rows, in batches,
          through the ORM and returns the number of rows updated. At least one criterion is required.
        """

    # ------------------------------------------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------------------------------------------

    @abstractmethod
    def delete_single(self, entity: TEntity) -> None:
        """Stage the deletion of an entity (not persisted). A staged, never saved entity is simply dropped."""

    @abstractmethod
    async def delete_single_async(self, entity: TEntity) -> None:
        """Delete an entity at once, in its own transaction. Nothing happens if the row no longer exists."""

    @abstractmethod
    def delete_by_id(self, entity_id: EntityId) -> None:
        """Stage the deletion of the entity with this primary key (not persisted). When the unit of work saves,
        the row is loaded and deleted through the ORM; a row that does not exist is reported in
        ``SaveChangesResult.not_found``."""

    @abstractmethod
    async def delete_by_id_async(self, entity_id: EntityId) -> bool:
        """Delete the entity with this primary key at once, in its own transaction; False if it does not exist."""

    @overload
    def delete_range(self, entities: Iterable[TEntity], /) -> int: ...

    @overload
    def delete_range(self, *criteria: Criterion) -> None: ...

    @abstractmethod
    def delete_range(self, *args: Any) -> int | None:
        """Stage the deletion of many entities (not persisted).

        * ``delete_range(entities)``: delete_single() for each entity; returns the number of entities.
        * ``delete_range(*criteria)``: when the unit of work saves, the matching rows are loaded in batches and
          deleted through the ORM. At least one criterion is required.
        """

    @overload
    async def delete_range_async(self, entities: Iterable[TEntity], /) -> int: ...

    @overload
    async def delete_range_async(self, *criteria: Criterion) -> int: ...

    @abstractmethod
    async def delete_range_async(self, *args: Any) -> int:
        """Delete many entities (or the rows matching the criteria, in batches) at once, in one transaction of
        their own, through the ORM; returns the number of rows deleted. Criteria need at least one criterion."""

    # ------------------------------------------------------------------------------------------------------
    # Save (add or update)
    # ------------------------------------------------------------------------------------------------------

    @abstractmethod
    def save(self, entity: TEntity) -> TEntity:
        """Stage an entity (not persisted): added when new, updated when it exists. Returns the entity the unit
        of work tracks.

        An entity loaded from the database (or already saved) exists. A new entity without a primary key value
        is added. A new entity whose primary key is set (e.g. built from request data) updates the tracked row
        with that key; if the unit of work does not track it, the database decides when the unit of work
        saves: the row is updated with the entity's values if it exists, inserted otherwise.
        """

    @abstractmethod
    async def save_async(self, entity: TEntity) -> TEntity:
        """Persist an entity at once: inserted when new, updated when it exists (same rules as save(), with the
        existence of a primary key that is set checked in the database)."""
