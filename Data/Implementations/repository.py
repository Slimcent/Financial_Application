"""SQLAlchemy 2.x (AsyncSession) implementation of IRepository, and the state it shares with its unit of work.

See Data/Interfaces/i_repository.py for the naming convention and the meaning of criteria, includes and
ordering. Everything a repository does happens on the session of the unit of work that created it:

* queries run on it directly;
* staged (non-persisting) operations are recorded, in call order, in the unit of work's PendingWork and applied
  to the session when the unit of work saves;
* ``_async`` add / update / delete / save set the unit of work's staged objects aside (_Stash), do their work
  and commit on that same session - so there is no second connection that could wait on the unit of work's
  row locks - and then put the staged objects back, with their changes.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from functools import partial
from typing import Any, TypeVar, cast, overload

from sqlalchemy import ColumnElement, Select, func, inspect as sa_inspect, select
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import (Mapper, QueryableAttribute, RelationshipDirection, RelationshipProperty, joinedload,
                            make_transient_to_detached, selectinload)
from sqlalchemy.orm.attributes import flag_modified, set_committed_value
from sqlalchemy.orm.interfaces import LoaderOption

from Data.Interfaces.i_repository import (Criterion, EntityId, Include, IRepository, Number, OrderBy, TEntity,
                                          Values)
from Models.Dtos.Response.paged_response import PagedResponse

# Rows loaded, written or deleted per round trip by bulk operations.
DEFAULT_BATCH_SIZE = 500

# A staged operation that needs the database: it is given the unit of work's session when it saves.
StagedOperation = Callable[[AsyncSession], Awaitable[None]]

# Identity of a row in a session: (entity class, primary key tuple, identity token).
IdentityKey = tuple[Any, ...]

_T = TypeVar("_T")

# Marks an attribute that was not loaded when a staged update changed it.
_UNLOADED: Any = object()


# ==========================================================================================================
# State shared by a unit of work and its repositories
# ==========================================================================================================

class RepositoryContext:
    """What the repositories of one unit of work share: its session, its staged work and the batch size.

    Closed when the unit of work ends; a repository used after that raises instead of working on a session
    that nobody would close again.
    """

    def __init__(self, session: AsyncSession, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self._session: AsyncSession | None = session
        self.batch_size = batch_size
        self.pending_work = PendingWork(batch_size)

    @property
    def session(self) -> AsyncSession:
        self.ensure_active()
        return cast(AsyncSession, self._session)

    @property
    def is_active(self) -> bool:
        return self._session is not None

    def ensure_active(self) -> None:
        if self._session is None:
            raise RuntimeError("the unit of work of this repository has ended; "
                               "use the repositories of an active unit of work")

    def close(self) -> AsyncSession | None:
        """End the context; returns the session so the unit of work can close it."""
        session, self._session = self._session, None
        self.pending_work.clear()
        return session


_ADD, _UPDATE, _DELETE, _OPERATION = "add", "update", "delete", "operation"


@dataclass(eq=False)
class _Entry:
    """One staged operation, in call order."""

    kind: str
    entity: Any = None
    values: dict[str, Any] = field(default_factory=dict)
    originals: dict[str, Any] = field(default_factory=dict)
    operation: StagedOperation | None = None


class PendingWork:
    """The operations staged through the repositories of one unit of work, in call order.

    ``apply_async()`` writes them to the open transaction (flush) when the unit of work saves. Values staged
    by update_single() are applied to the entity at once, so it shows them; when operations that need the
    database (criteria-based update / delete, delete by id, save of a new entity with a key) are staged too,
    those values are taken back first and every operation is applied in the order it was called.
    """

    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        self._batch_size = batch_size
        self._entries: list[_Entry] = []
        self._new: dict[int, Any] = {}         # new entities staged for insertion (id -> entity)
        self._refreshes: dict[int, Any] = {}   # entities whose expired columns are reloaded after saving
        self._not_found: list[tuple[str, Any]] = []

    # -- staging ------------------------------------------------------------------------------------------

    def stage_add(self, entity: Any) -> None:
        if id(entity) not in self._new:
            self._new[id(entity)] = entity
            self._entries.append(_Entry(_ADD, entity))

    def stage_update(self, entity: Any, values: dict[str, Any], originals: dict[str, Any]) -> None:
        self._entries.append(_Entry(_UPDATE, entity, values=values, originals=originals))

    def stage_delete(self, entity: Any) -> None:
        self._entries.append(_Entry(_DELETE, entity))

    def stage_operation(self, operation: StagedOperation, entity: Any = None, *, new: bool = False) -> None:
        if new:
            self._new[id(entity)] = entity
        self._entries.append(_Entry(_OPERATION, entity, operation=operation))

    def add_refresh(self, entities: Iterable[Any]) -> None:
        for entity in entities:
            self._refreshes[id(entity)] = entity

    def record_not_found(self, entity_name: str, entity_id: Any) -> None:
        self._not_found.append((entity_name, entity_id))

    # -- inspection / removal -----------------------------------------------------------------------------

    def is_staged_new(self, entity: Any) -> bool:
        return id(entity) in self._new

    def unstage(self, entity: Any) -> None:
        """Forget everything staged for this entity (it was persisted or deleted by an _async operation)."""
        self._entries = [entry for entry in self._entries if entry.entity is not entity]
        self._new.pop(id(entity), None)
        self._refreshes.pop(id(entity), None)

    def discard_updates(self, entity: Any, names: Iterable[str]) -> None:
        """Forget the staged updates of these attributes of an entity (an _async operation has written them);
        staged updates of its other attributes stay."""
        written = set(names)
        kept = []
        for entry in self._entries:
            if entry.kind == _UPDATE and entry.entity is entity:
                entry.values = {name: value for name, value in entry.values.items() if name not in written}
                entry.originals = {name: value for name, value in entry.originals.items() if name not in written}
                if not entry.values:
                    continue
            kept.append(entry)
        self._entries = kept

    def unstage_rows(self, keys: Iterable[IdentityKey]) -> None:
        """Forget everything staged for entities whose rows were deleted by an _async operation."""
        deleted = set(keys)
        if not deleted:
            return
        kept = []
        for entry in self._entries:
            if entry.entity is not None and sa_inspect(entry.entity).key in deleted:
                self._new.pop(id(entry.entity), None)
                self._refreshes.pop(id(entry.entity), None)
                continue
            kept.append(entry)
        self._entries = kept

    def clear(self) -> None:
        self._entries.clear()
        self._new.clear()
        self._refreshes.clear()
        self._not_found.clear()

    # -- saving -------------------------------------------------------------------------------------------

    async def apply_async(self, session: AsyncSession) -> tuple[tuple[str, Any], ...]:
        """Write every staged operation to the open transaction (flush), in call order; nothing is committed.

        Returns the (entity name, id) of rows that delete_by_id() did not find.
        """
        entries, self._entries = self._entries, []
        self._new.clear()

        in_call_order = any(entry.kind == _OPERATION for entry in entries)
        if in_call_order:
            for entry in reversed(entries):
                if entry.kind == _UPDATE and entry.entity in session:
                    _revert(session, entry)

        for entry in entries:
            if entry.kind == _ADD:
                if sa_inspect(entry.entity).key is None:  # not inserted by an _async operation meanwhile
                    _reconcile_graph(session, entry.entity)
                    session.add(entry.entity)
            elif entry.kind == _UPDATE:
                if in_call_order and entry.entity in session:
                    _assign([entry.entity], entry.values)
            elif entry.kind == _DELETE:
                if entry.entity in session:
                    await session.delete(entry.entity)
            elif entry.operation is not None:
                await session.flush()  # everything staged before the operation is visible to its query
                await entry.operation(session)
        await session.flush()

        refreshes, self._refreshes = list(self._refreshes.values()), {}
        await _reload_expired_async(session, [entity for entity in refreshes if entity in session],
                                    self._batch_size)
        not_found, self._not_found = tuple(self._not_found), []
        return not_found


class LoadedState:
    """The values the entities of a session were loaded with (staged changes left out).

    A rollback expires every entity the session tracks, so reading one afterwards would need the database
    (which fails in async code). restore() - called after the rollback - puts these values back, so entities
    stay usable, and drops the entities that were loaded after the snapshot was taken.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._entries: list[tuple[Any, dict[str, Any]]] = []
        for state in list(session.sync_session.identity_map.all_states()):
            entity = state.obj()
            if entity is None:
                continue
            values: dict[str, Any] = {}
            for prop in state.mapper.column_attrs:
                if prop.key in state.dict:
                    original = state.attrs[prop.key].history.non_added()
                    values[prop.key] = original[0] if original else None
            for relationship in state.mapper.relationships:
                if relationship.key in state.dict:
                    original = state.attrs[relationship.key].history.non_added()
                    if relationship.uselist:
                        values[relationship.key] = list(original)
                    else:
                        values[relationship.key] = original[0] if original else None
            self._entries.append((entity, values))

    def restore(self, session: AsyncSession) -> None:
        sync = session.sync_session
        known: set[int] = set()
        for entity, values in self._entries:
            known.add(id(entity))
            if entity not in sync:
                continue
            for key, value in values.items():
                set_committed_value(entity, key, value)
        for state in list(sync.identity_map.all_states()):
            entity = state.obj()
            if entity is not None and id(entity) not in known:
                sync.expunge(entity)


class _Stash:
    """The objects a session holds changes for (new, changed, deleted), set aside - expunged - so that a
    commit on the session writes none of them; restore() puts them back with their changes."""

    def __init__(self, session: AsyncSession) -> None:
        sync = session.sync_session
        self._new = list(sync.new)
        self._dirty = list(sync.dirty)
        self._deleted = list(sync.deleted)
        for entity in (*self._new, *self._dirty, *self._deleted):
            sync.expunge(entity)
        self.keys = frozenset(key for entity in (*self._dirty, *self._deleted)
                              if (key := sa_inspect(entity).key) is not None)

    def restore(self, session: AsyncSession, deleted_keys: frozenset[IdentityKey],
                pending_work: PendingWork) -> None:
        sync = session.sync_session
        for entity in (*self._dirty, *self._deleted):
            key = sa_inspect(entity).key
            if key in deleted_keys:
                pending_work.unstage(entity)  # its row was deleted: nothing left to save for it
                continue
            present = sync.identity_map.get(key)
            if present is not None and present is not entity:
                sync.expunge(present)
            if entity not in sync:
                sync.add(entity)
        for entity in self._deleted:
            if sa_inspect(entity).key not in deleted_keys and entity in sync:
                sync.delete(entity)
        for entity in self._new:
            if entity not in sync:
                sync.add(entity)


@dataclass(eq=False)
class _Outcome:
    """What an _async write did, for the fix-ups made once the staged objects are back."""

    result: Any = None
    snapshots: dict[IdentityKey, dict[str, Any]] = field(default_factory=dict)  # stored values per row
    deleted: set[IdentityKey] = field(default_factory=set)
    originals: set[int] = field(default_factory=set)  # ids of the given entities, brought up to date by `after`
    after: list[Callable[[], None]] = field(default_factory=list)


@dataclass(eq=False)
class _UpdatePlan:
    """One entity of update_*_async: the column values to write for its row."""

    entity: Any
    key: IdentityKey
    changes: dict[str, Any]       # column values, foreign keys of changed many-to-one relationships included
    many_to_one: dict[str, Any]   # the changed many-to-one relationships behind those foreign keys


# ==========================================================================================================
# Repository
# ==========================================================================================================

class Repository(IRepository[TEntity]):
    """CRUD operations and queries for one entity type, within a unit of work."""

    def __init__(self, model: type[TEntity], context: RepositoryContext) -> None:
        mapper: Mapper[Any] = sa_inspect(model)
        if len(mapper.primary_key) != 1:
            raise TypeError(f"{model.__name__} must have a single-column primary key")

        self._model = model
        self._context = context
        self._mapper = mapper
        self._primary_key_name = mapper.get_property_by_column(mapper.primary_key[0]).key
        self._primary_key: QueryableAttribute[Any] = getattr(model, self._primary_key_name)
        self._column_keys = tuple(prop.key for prop in mapper.column_attrs)
        self._many_to_one = {relationship.key: relationship for relationship in mapper.relationships
                             if relationship.direction is RelationshipDirection.MANYTOONE}

    @property
    def model(self) -> type[TEntity]:
        return self._model

    @property
    def _session(self) -> AsyncSession:
        return self._context.session  # raises once the unit of work has ended

    @property
    def _pending_work(self) -> PendingWork:
        self._context.ensure_active()  # staging on an ended unit of work would be lost silently
        return self._context.pending_work

    @property
    def _batch_size(self) -> int:
        return self._context.batch_size

    # ------------------------------------------------------------------------------------------------------
    # Query building
    # ------------------------------------------------------------------------------------------------------

    def query(self) -> Select[Any]:
        return select(self._model)

    # ------------------------------------------------------------------------------------------------------
    # Get (single)
    # ------------------------------------------------------------------------------------------------------

    async def get_by_id_async(self, entity_id: EntityId, *, includes: Sequence[Include] = (),
                              for_update: bool = False) -> TEntity | None:
        statement = self.query().where(self._primary_key == entity_id)
        return await self._one_or_none_async(statement, includes, for_update)

    @overload
    async def get_single_async(self, *criteria: Criterion, includes: Sequence[Include] = (),
                               for_update: bool = False) -> TEntity | None: ...

    @overload
    async def get_single_async(self, statement: Select[Any], /, *, includes: Sequence[Include] = (),
                               for_update: bool = False) -> TEntity | None: ...

    async def get_single_async(self, *criteria: Any, includes: Sequence[Include] = (),
                               for_update: bool = False) -> TEntity | None:
        if not criteria:
            raise ValueError("get_single_async needs a filter: at least one criterion or a statement")
        statement = self._statement_from(criteria)
        if statement.whereclause is None:
            raise ValueError("get_single_async needs a filter: the statement has no WHERE clause")
        return await self._one_or_none_async(statement, includes, for_update)

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

    async def get_range_async(self, *criteria: Any, includes: Sequence[Include] = (),
                              order_by: Sequence[OrderBy] = (), skip: int | None = None, take: int | None = None,
                              for_update: bool = False, page: int | None = None, page_size: int | None = None
                              ) -> list[TEntity] | PagedResponse[TEntity]:
        statement = self._statement_from(criteria)

        if page is None and page_size is None:
            statement = self._prepare(statement, includes, order_by, for_update)
            if skip is not None:
                statement = statement.offset(_non_negative("skip", skip))
            if take is not None:
                statement = statement.limit(_non_negative("take", take))
            return await self._fetch_async(statement, for_update)

        if page is None or page_size is None:
            raise ValueError("page and page_size must be given together")
        if skip is not None or take is not None:
            raise ValueError("use either page / page_size or skip / take, not both")
        if for_update:
            raise ValueError("for_update cannot be combined with paging")
        if page < 1 or page_size < 1:
            raise ValueError("page and page_size must be at least 1")

        total_count = await self._count_async(statement)
        # The primary key is the last ordering term, so rows with equal sort values keep a stable page.
        ordering = (*_as_sequence(order_by), self._primary_key)
        page_statement = (self._prepare(statement, includes, ordering, False)
                          .offset((page - 1) * page_size)
                          .limit(page_size))
        items = await self._fetch_async(page_statement, False)
        return PagedResponse(total_count=total_count, page=page, page_size=page_size, items=items)

    # ------------------------------------------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------------------------------------------

    @overload
    async def count_async(self, *criteria: Criterion) -> int: ...

    @overload
    async def count_async(self, statement: Select[Any], /) -> int: ...

    async def count_async(self, *criteria: Any) -> int:
        return await self._count_async(self._statement_from(criteria))

    @overload
    async def sum_async(self, column: QueryableAttribute[Any] | ColumnElement[Any],
                        *criteria: Criterion) -> Number: ...

    @overload
    async def sum_async(self, column: QueryableAttribute[Any] | ColumnElement[Any],
                        statement: Select[Any], /) -> Number: ...

    async def sum_async(self, column: QueryableAttribute[Any] | ColumnElement[Any], *criteria: Any) -> Number:
        # The entity SELECT (criteria or a statement from query()) with its columns replaced by the sum; its FROM
        # clause and joins are kept. Ordering, offset and limit are dropped, as for count_async().
        statement = (self._statement_from(criteria)
                     .with_only_columns(func.coalesce(func.sum(column), 0), maintain_column_froms=True)
                     .order_by(None).limit(None).offset(None))
        return cast(Number, await self._session.scalar(statement))

    @overload
    async def exists_async(self, *criteria: Criterion) -> bool: ...

    @overload
    async def exists_async(self, statement: Select[Any], /) -> bool: ...

    async def exists_async(self, *criteria: Any) -> bool:
        statement = self._statement_from(criteria).order_by(None)
        return bool(await self._session.scalar(select(statement.exists())))

    # ------------------------------------------------------------------------------------------------------
    # Add
    # ------------------------------------------------------------------------------------------------------

    def add_single(self, entity: TEntity) -> TEntity:
        return self.add_range([entity])[0]

    async def add_single_async(self, entity: TEntity) -> TEntity:
        return (await self.add_range_async([entity]))[0]

    def add_range(self, entities: Iterable[TEntity]) -> list[TEntity]:
        pending_work = self._pending_work
        entity_list = self._entity_list(entities)
        for entity in entity_list:
            self._ensure_new(entity)
        for entity in entity_list:
            pending_work.stage_add(entity)
        pending_work.add_refresh(entity_list)
        return entity_list

    async def add_range_async(self, entities: Iterable[TEntity]) -> list[TEntity]:
        self._context.ensure_active()
        entity_list = self._entity_list(entities)
        for entity in entity_list:
            self._ensure_new(entity)
            if not self._is_staged_new(entity):
                self._ensure_nothing_related_to_save(entity)
        row_values = [self._insert_values(entity) for entity in entity_list]

        async def write(session: AsyncSession, stashed: frozenset[IdentityKey]) -> _Outcome:
            outcome = _Outcome(result=entity_list)
            for chunk in _chunks(list(zip(entity_list, row_values)), self._batch_size):
                rows = [self._model(**values) for _, values in chunk]
                session.add_all(rows)
                await session.flush()
                await _reload_expired_async(session, rows, self._batch_size)
                for (entity, _), row in zip(chunk, rows):
                    snapshot = self._column_snapshot(row)
                    outcome.originals.add(id(entity))
                    outcome.after.append(partial(self._mark_saved, entity, snapshot))
                    session.expunge(row)  # the given entity, not this copy, represents the row from now on
            return outcome

        return cast(list[TEntity], await self._run_isolated_async(write))

    # ------------------------------------------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------------------------------------------

    def update_single(self, entity: TEntity, values: Values | None = None) -> TEntity:
        pending_work = self._pending_work
        self._ensure_entity(entity)
        if values:
            self._check_attribute_names(values, columns_only=False)

        if sa_inspect(entity).key is None:
            if not self._is_staged_new(entity):
                raise ValueError(f"this {self._model.__name__} has not been saved yet; use add_single or save")
            _assign([entity], self._resolved_values(values or {}))  # part of its insert
            return entity

        tracked = self._track(entity)
        if values:
            resolved = self._resolved_values(values)
            tracked_state = sa_inspect(tracked)
            originals = {name: _current_value(tracked_state, name) for name in resolved}
            _assign([tracked], resolved)
            pending_work.stage_update(tracked, resolved, originals)
            pending_work.add_refresh([tracked])
        return tracked

    async def update_single_async(self, entity: TEntity, values: Values | None = None) -> TEntity:
        return (await self.update_range_async([entity], values=values))[0]

    @overload
    def update_range(self, entities: Iterable[TEntity], /, *, values: Values | None = None) -> list[TEntity]: ...

    @overload
    def update_range(self, *criteria: Criterion, values: Values) -> None: ...

    def update_range(self, *args: Any, values: Values | None = None) -> list[TEntity] | None:
        pending_work = self._pending_work
        if not _is_criteria_form(args, values):
            return [self.update_single(entity, values) for entity in self._entity_list(_single_iterable(args))]

        criteria, update_values = self._criteria_update(args, values)

        async def operation(session: AsyncSession) -> None:
            await self._update_where_async(session, criteria, update_values, frozenset())

        pending_work.stage_operation(operation)
        return None

    @overload
    async def update_range_async(self, entities: Iterable[TEntity], /, *,
                                 values: Values | None = None) -> list[TEntity]: ...

    @overload
    async def update_range_async(self, *criteria: Criterion, values: Values) -> int: ...

    async def update_range_async(self, *args: Any, values: Values | None = None) -> list[TEntity] | int:
        self._context.ensure_active()
        if _is_criteria_form(args, values):
            criteria, update_values = self._criteria_update(args, values)

            async def write_matching(session: AsyncSession, stashed: frozenset[IdentityKey]) -> _Outcome:
                count, snapshots = await self._update_where_async(session, criteria, update_values, stashed)
                return _Outcome(result=count, snapshots=snapshots)

            return cast(int, await self._run_isolated_async(write_matching))

        entity_list = self._entity_list(_single_iterable(args))
        if values:
            self._check_attribute_names(values, columns_only=False)
        plans = [self._update_plan(entity, values) for entity in entity_list]
        to_write = [plan for plan in plans if plan.changes]
        if not to_write:
            return entity_list  # nothing to write for these rows

        async def write(session: AsyncSession, stashed: frozenset[IdentityKey]) -> _Outcome:
            tracked_before = _tracked_keys(session)
            outcome = _Outcome(result=entity_list)
            for chunk in _chunks(to_write, self._batch_size):
                rows = await self._rows_by_keys_async(session, [plan.key for plan in chunk])
                for plan in chunk:
                    row = rows.get(plan.key)
                    if row is None:
                        raise ValueError(f"{self._model.__name__} {plan.key[1][0]} no longer exists")
                    _assign([row], plan.changes)
                await session.flush()
                await _reload_expired_async(session, list(rows.values()), self._batch_size)
                for plan in chunk:
                    snapshot = self._column_snapshot(rows[plan.key])
                    outcome.snapshots[plan.key] = snapshot
                    outcome.originals.add(id(plan.entity))
                    outcome.after.append(partial(self._mark_updated, plan, snapshot))
                for key, row in rows.items():
                    if key not in tracked_before:
                        session.expunge(row)
            return outcome

        return cast(list[TEntity], await self._run_isolated_async(write))

    # ------------------------------------------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------------------------------------------

    def delete_single(self, entity: TEntity) -> None:
        pending_work = self._pending_work
        self._ensure_entity(entity)
        if self._drop_if_staged_new(entity):
            return
        pending_work.stage_delete(self._track(entity))

    async def delete_single_async(self, entity: TEntity) -> None:
        await self.delete_range_async([entity])

    def delete_by_id(self, entity_id: EntityId) -> None:
        pending_work = self._pending_work
        entity_name = self._model.__name__

        async def operation(session: AsyncSession) -> None:
            row = await session.get(self._model, entity_id)
            if row is None:
                pending_work.record_not_found(entity_name, entity_id)
            else:
                await session.delete(row)

        pending_work.stage_operation(operation)

    async def delete_by_id_async(self, entity_id: EntityId) -> bool:
        key = self._mapper.identity_key_from_primary_key((entity_id,))
        return await self._delete_keys_async([key]) == 1

    @overload
    def delete_range(self, entities: Iterable[TEntity], /) -> int: ...

    @overload
    def delete_range(self, *criteria: Criterion) -> None: ...

    def delete_range(self, *args: Any) -> int | None:
        pending_work = self._pending_work
        if not _is_criteria_form(args, None):
            entity_list = self._entity_list(_single_iterable(args))
            for entity in entity_list:
                self.delete_single(entity)
            return len(entity_list)

        criteria = _required_criteria(args, "delete")

        async def operation(session: AsyncSession) -> None:
            await self._delete_where_async(session, criteria)

        pending_work.stage_operation(operation)
        return None

    @overload
    async def delete_range_async(self, entities: Iterable[TEntity], /) -> int: ...

    @overload
    async def delete_range_async(self, *criteria: Criterion) -> int: ...

    async def delete_range_async(self, *args: Any) -> int:
        session = self._session
        if _is_criteria_form(args, None):
            criteria = _required_criteria(args, "delete")

            async def write(session: AsyncSession, stashed: frozenset[IdentityKey]) -> _Outcome:
                deleted = await self._delete_where_async(session, criteria)
                return _Outcome(result=len(deleted), deleted=set(deleted))

            return cast(int, await self._run_isolated_async(write))

        keys = []
        for entity in self._entity_list(_single_iterable(args)):
            if self._drop_if_staged_new(entity):
                continue  # never saved: nothing to delete in the database
            state = sa_inspect(entity)
            if state.session is not None and state.session is not session.sync_session:
                raise ValueError(f"this {self._model.__name__} belongs to another session")
            keys.append(_identity_key(entity))
        return await self._delete_keys_async(keys)

    # ------------------------------------------------------------------------------------------------------
    # Save (add or update)
    # ------------------------------------------------------------------------------------------------------

    def save(self, entity: TEntity) -> TEntity:
        pending_work = self._pending_work
        self._ensure_entity(entity)
        state = sa_inspect(entity)
        if state.key is not None:
            return self.update_single(entity)
        if self._is_staged_new(entity):
            return entity  # already staged
        self._ensure_new(entity)

        entity_id = state.dict.get(self._primary_key_name)
        if entity_id is None:
            return self.add_single(entity)

        key = self._mapper.identity_key_from_primary_key((entity_id,))
        tracked = self._session.sync_session.identity_map.get(key)
        if tracked is not None:
            return self.update_single(cast(TEntity, tracked), self._values_of_new(entity))

        async def operation(session: AsyncSession) -> None:
            existing = await session.get(self._model, entity_id)
            if existing is None:
                _reconcile_graph(session, entity)
                session.add(entity)
                pending_work.add_refresh([entity])
            else:
                _assign([existing], self._values_of_new(entity))
                pending_work.add_refresh([existing])

        pending_work.stage_operation(operation, entity, new=True)
        return entity

    async def save_async(self, entity: TEntity) -> TEntity:
        self._ensure_entity(entity)
        state = sa_inspect(entity)
        if state.key is not None:
            return await self.update_single_async(entity)
        self._ensure_new(entity)

        entity_id = state.dict.get(self._primary_key_name)
        if entity_id is None:
            return await self.add_single_async(entity)

        if not self._is_staged_new(entity):
            self._ensure_nothing_related_to_save(entity)
        key = self._mapper.identity_key_from_primary_key((entity_id,))

        async def write(session: AsyncSession, stashed: frozenset[IdentityKey]) -> _Outcome:
            tracked_before = _tracked_keys(session)
            existing = await session.get(self._model, entity_id)
            if existing is None:
                row = self._model(**self._insert_values(entity))
                session.add(row)
            else:
                row = existing
                _assign([row], self._values_of_new(entity))
            await session.flush()
            await _reload_expired_async(session, [row], self._batch_size)
            snapshot = self._column_snapshot(row)
            outcome = _Outcome(result=entity)
            if existing is not None:
                outcome.snapshots[key] = snapshot
            if key not in tracked_before:
                session.expunge(row)
            outcome.originals.add(id(entity))
            outcome.after.append(partial(self._mark_saved, entity, snapshot))
            return outcome

        return cast(TEntity, await self._run_isolated_async(write))

    # ------------------------------------------------------------------------------------------------------
    # Statement helpers
    # ------------------------------------------------------------------------------------------------------

    def _statement_from(self, criteria: tuple[Any, ...]) -> Select[Any]:
        """The statement passed in, or a SELECT of the entity filtered by the criteria."""
        if len(criteria) == 1 and isinstance(criteria[0], Select):
            statement = criteria[0]
            descriptions = statement.column_descriptions
            if len(descriptions) != 1 or descriptions[0].get("entity") is not self._model:
                raise TypeError(f"the statement must select only {self._model.__name__} entities "
                                f"(build it from query())")
            return statement
        _validate_criteria(criteria)
        return self.query().where(*criteria)

    def _prepare(self, statement: Select[Any], includes: Sequence[Include] | Include,
                 order_by: Sequence[OrderBy] | OrderBy, for_update: bool) -> Select[Any]:
        """Apply includes, ordering and row locking to a SELECT of the entity."""
        options = self._loader_options(includes)
        if options:
            statement = statement.options(*options)
        ordering = _as_sequence(order_by)
        if ordering:
            statement = statement.order_by(*ordering)
        if for_update:
            # Lock only this entity's rows (FOR UPDATE OF on MySQL 8), not the rows of joined includes.
            statement = statement.with_for_update(of=self._model)
        return statement

    async def _fetch_async(self, statement: Select[Any], for_update: bool) -> list[TEntity]:
        session = self._session
        tracked_before = _tracked_keys(session) if for_update else frozenset()
        result = await session.scalars(statement)
        rows = list(result.unique().all())
        if for_update and tracked_before:
            already_tracked = [row for row in rows if _identity_key(row) in tracked_before]
            await self._refresh_locked_columns_async(session, already_tracked)
        return rows

    async def _one_or_none_async(self, statement: Select[Any], includes: Sequence[Include] | Include,
                                 for_update: bool) -> TEntity | None:
        # Two rows are enough to tell "exactly one" from "more than one".
        rows = await self._fetch_async(self._prepare(statement, includes, (), for_update).limit(2), for_update)
        if len(rows) > 1:
            raise MultipleResultsFound(f"more than one {self._model.__name__} matches the filter; "
                                       f"get_single_async needs a filter that identifies one row")
        return rows[0] if rows else None

    async def _count_async(self, statement: Select[Any]) -> int:
        counted = statement.order_by(None).limit(None).offset(None).subquery()
        return int(await self._session.scalar(select(func.count()).select_from(counted)) or 0)

    async def _refresh_locked_columns_async(self, session: AsyncSession, entities: list[TEntity]) -> None:
        """Give entities that were already tracked the column values of the rows just locked.

        Only columns are read (a plain load would keep the stale values, and populate_existing would drop
        staged changes and loaded relationships). A column with a staged change keeps it on top of the new
        value.
        """
        columns = [getattr(self._model, key) for key in self._column_keys]
        key_position = self._column_keys.index(self._primary_key_name)
        for chunk in _chunks(entities, self._batch_size):
            ids = [_primary_key_value(entity) for entity in chunk]
            result = await session.execute(select(*columns).where(self._primary_key.in_(ids)))
            fresh = {row[key_position]: row for row in result.all()}
            for entity in chunk:
                state = sa_inspect(entity)
                row = fresh.get(_primary_key_value(entity))
                if row is None:
                    continue
                for position, key in enumerate(self._column_keys):
                    staged = list(state.attrs[key].history.added or ())
                    set_committed_value(entity, key, row[position])
                    if staged:
                        setattr(entity, key, staged[0])

    async def _for_each_batch_async(self, session: AsyncSession, criteria: tuple[Any, ...],
                                    handle: Callable[[list[TEntity]], Awaitable[None]]) -> None:
        """Load the rows matching the criteria in primary-key order, one batch at a time, and hand each batch
        to `handle` before loading the next. Keyset paging on the primary key: rows that no longer match after
        `handle` changed them, or that it deleted, do not shift the following batches."""
        last_id: Any = None
        while True:
            statement = self.query().where(*criteria)
            if last_id is not None:
                statement = statement.where(self._primary_key > last_id)
            statement = statement.order_by(self._primary_key).limit(self._batch_size)
            rows = list((await session.scalars(statement)).unique().all())
            if not rows:
                return
            last_id = _primary_key_value(rows[-1])
            await handle(rows)
            if len(rows) < self._batch_size:
                return

    async def _rows_by_keys_async(self, session: AsyncSession, keys: list[IdentityKey]) -> dict[IdentityKey, Any]:
        if not keys:
            return {}
        ids = [key[1][0] for key in keys]
        result = await session.scalars(self.query().where(self._primary_key.in_(ids)))
        return {_identity_key(row): row for row in result.unique().all()}

    async def _update_where_async(self, session: AsyncSession, criteria: tuple[Any, ...], values: dict[str, Any],
                                  wanted: frozenset[IdentityKey]) -> tuple[int, dict[IdentityKey, dict[str, Any]]]:
        """Apply `values` to the rows matching the criteria through the ORM, batch by batch. Rows the session
        did not track before are let go after each batch. Returns the number of rows and the stored values of
        the rows in `wanted`."""
        tracked_before = _tracked_keys(session)
        snapshots: dict[IdentityKey, dict[str, Any]] = {}
        count = 0

        async def handle(batch: list[TEntity]) -> None:
            nonlocal count
            _assign(batch, values)
            await session.flush()
            keys = [_identity_key(row) for row in batch]
            await _reload_expired_async(session, [row for row, key in zip(batch, keys)
                                                  if key in tracked_before or key in wanted], self._batch_size)
            for row, key in zip(batch, keys):
                if key in wanted:
                    snapshots[key] = self._column_snapshot(row)
                if key not in tracked_before:
                    session.expunge(row)
            count += len(batch)

        await self._for_each_batch_async(session, criteria, handle)
        return count, snapshots

    async def _delete_where_async(self, session: AsyncSession, criteria: tuple[Any, ...]) -> list[IdentityKey]:
        """Delete the rows matching the criteria through the ORM, batch by batch; returns their identities."""
        deleted: list[IdentityKey] = []

        async def handle(batch: list[TEntity]) -> None:
            for row in batch:
                deleted.append(_identity_key(row))
                await session.delete(row)
            await session.flush()

        await self._for_each_batch_async(session, criteria, handle)
        return deleted

    async def _delete_keys_async(self, keys: list[IdentityKey]) -> int:
        unique_keys = list(dict.fromkeys(keys))
        if not unique_keys:
            return 0

        async def write(session: AsyncSession, stashed: frozenset[IdentityKey]) -> _Outcome:
            outcome = _Outcome()
            for chunk in _chunks(unique_keys, self._batch_size):
                rows = await self._rows_by_keys_async(session, chunk)
                for key, row in rows.items():
                    await session.delete(row)
                    outcome.deleted.add(key)
                await session.flush()
            outcome.result = len(outcome.deleted)
            return outcome

        return cast(int, await self._run_isolated_async(write))

    # ------------------------------------------------------------------------------------------------------
    # _async operations: own transaction on the unit of work's session
    # ------------------------------------------------------------------------------------------------------

    async def _run_isolated_async(self, write: Callable[[AsyncSession, frozenset[IdentityKey]],
                                                        Awaitable[_Outcome]]) -> Any:
        """Run `write` and commit it on the unit of work's session, with the unit of work's staged objects set
        aside, so that only the data of the _async operation is committed.

        Using the unit of work's own session (its connection) means the operation can never wait on row locks
        the unit of work holds. The commit ends the unit of work's current transaction, which only holds reads
        (staged changes are never written before save_changes_async). On failure the transaction is rolled
        back, tracked entities keep their loaded values and the staged objects are put back unchanged.
        """
        session = self._session
        pending_work = self._context.pending_work
        stash = _Stash(session)
        loaded = LoadedState(session)
        try:
            outcome = await write(session, stash.keys)
            await session.commit()
        except BaseException:
            try:
                await session.rollback()
                loaded.restore(session)
            finally:
                stash.restore(session, frozenset(), pending_work)
            raise

        deleted = frozenset(outcome.deleted)
        stash.restore(session, deleted, pending_work)
        pending_work.unstage_rows(deleted)
        for bring_up_to_date in outcome.after:
            bring_up_to_date()
        for key, snapshot in outcome.snapshots.items():
            self._sync_tracked(key, snapshot, exclude=outcome.originals)
        return outcome.result

    def _update_plan(self, entity: TEntity, values: Values | None) -> _UpdatePlan:
        """The column values update_*_async writes for one entity: its changed columns, the foreign keys of
        its changed many-to-one relationships, and `values`."""
        self._ensure_entity(entity)
        state = sa_inspect(entity)
        if state.key is None:
            raise ValueError(f"this {self._model.__name__} has not been saved yet; use an add or save operation")
        sync = self._session.sync_session
        if state.session is not None and state.session is not sync:
            raise ValueError(f"this {self._model.__name__} belongs to another session")
        tracked_here = state.session is sync

        columns, scalars, collections = self._pending_changes(entity)
        many_to_one = {name: target for name, target in scalars.items() if name in self._many_to_one}
        elsewhere = [name for name in scalars if name not in self._many_to_one] + list(collections)
        staged_values: dict[str, Any] = {}
        for name, value in (values or {}).items():
            if name in self._column_keys:
                columns[name] = value
            elif name in self._many_to_one:
                many_to_one[name] = value
            else:
                elsewhere.append(name)
                staged_values[name] = value

        if elsewhere and not tracked_here:
            raise ValueError(f"changes to {sorted(set(elsewhere))} of this {self._model.__name__} are stored in "
                             f"other rows and are not written by an _async update; this entity is not tracked "
                             f"by the unit of work, so they would be lost. Use update_single() and "
                             f"save_changes_async() instead")
        if staged_values:
            self.update_single(entity, staged_values)  # tracked here: they stay staged

        for name, target in many_to_one.items():
            columns.update(self._foreign_key_values(self._many_to_one[name], target))
        return _UpdatePlan(entity=entity, key=cast(IdentityKey, state.key), changes=columns,
                           many_to_one=many_to_one)

    def _mark_saved(self, entity: TEntity, snapshot: dict[str, Any]) -> None:
        """After an _async insert (or save): the entity gets the stored values and becomes an existing entity;
        it is tracked by the unit of work if it was staged there (and the row is not tracked already)."""
        session = self._session
        sync = session.sync_session
        state = sa_inspect(entity)
        staged = self._is_staged_new(entity)
        self._context.pending_work.unstage(entity)
        if state.session is sync:
            sync.expunge(entity)  # saved already: the unit of work must not insert it again
        for key, value in snapshot.items():
            set_committed_value(entity, key, value)
        make_transient_to_detached(entity)
        if staged and sync.identity_map.get(_identity_key(entity)) is None:
            _reconcile_graph(session, entity)
            sync.add(entity)

    def _mark_updated(self, plan: _UpdatePlan, snapshot: dict[str, Any]) -> None:
        """After an _async update: the entity gets the stored values; its written changes are no longer staged."""
        self._set_committed(plan.entity, snapshot, keep_changes=False)
        for name, target in plan.many_to_one.items():
            set_committed_value(plan.entity, name, target)
        self._context.pending_work.discard_updates(plan.entity, [*plan.changes, *plan.many_to_one])

    def _sync_tracked(self, key: IdentityKey, snapshot: dict[str, Any], *, exclude: set[int]) -> None:
        """Give the unit of work's instance of a row the values just stored (its staged changes are kept)."""
        tracked = self._session.sync_session.identity_map.get(key)
        if tracked is not None and id(tracked) not in exclude:
            self._set_committed(tracked, snapshot, keep_changes=True)

    # ------------------------------------------------------------------------------------------------------
    # Includes
    # ------------------------------------------------------------------------------------------------------

    def _loader_options(self, includes: Sequence[Include] | Include) -> list[LoaderOption]:
        if isinstance(includes, (str, QueryableAttribute, LoaderOption)):
            includes = [includes]  # a single include given without a list

        options: list[LoaderOption] = []
        for include in includes:
            if isinstance(include, LoaderOption):
                options.append(include)
            elif isinstance(include, str):
                options.append(_loader_for_path(self._path_from_string(include)))
            elif isinstance(include, QueryableAttribute):
                options.append(_loader_for_path(self._checked_path([include])))
            elif isinstance(include, Sequence) and include:
                options.append(_loader_for_path(self._checked_path(list(include))))
            else:
                raise TypeError(f"unsupported include: {include!r}")
        return options

    def _path_from_string(self, path: str) -> list[QueryableAttribute[Any]]:
        """"user.customer" -> [Account.user, User.customer] (for an Account repository)."""
        attributes: list[QueryableAttribute[Any]] = []
        mapper = self._mapper
        for name in path.split("."):
            relationship = mapper.relationships.get(name.strip())
            if relationship is None:
                raise ValueError(f"{mapper.class_.__name__} has no relationship '{name}' (include '{path}')")
            attributes.append(getattr(mapper.class_, relationship.key))
            mapper = relationship.mapper
        return attributes

    def _checked_path(self, path: list[Any]) -> list[QueryableAttribute[Any]]:
        """Check that each attribute is a relationship of the entity reached by the previous one."""
        mapper = self._mapper
        for attribute in path:
            relationship = getattr(attribute, "property", None)
            if (not isinstance(attribute, QueryableAttribute) or relationship is None
                    or relationship not in mapper.relationships.values()):
                raise ValueError(f"{attribute!r} is not a relationship of {mapper.class_.__name__}")
            mapper = relationship.mapper
        return path

    # ------------------------------------------------------------------------------------------------------
    # Entity helpers
    # ------------------------------------------------------------------------------------------------------

    def _ensure_entity(self, entity: Any) -> None:
        if not isinstance(entity, self._model):
            raise TypeError(f"expected a {self._model.__name__}, got {type(entity).__name__}")

    def _entity_list(self, entities: Iterable[TEntity]) -> list[TEntity]:
        entity_list = list(entities)
        for entity in entity_list:
            self._ensure_entity(entity)
        return entity_list

    def _ensure_new(self, entity: TEntity) -> None:
        state = sa_inspect(entity)
        if state.key is not None:
            raise ValueError(f"this {self._model.__name__} has already been saved; use an update operation")
        if state.session is not None and state.session is not self._session.sync_session:
            raise ValueError(f"this {self._model.__name__} belongs to another session")

    def _is_staged_new(self, entity: TEntity) -> bool:
        """A new entity staged in this unit of work: by add / save, or reached from a staged entity."""
        state = sa_inspect(entity)
        return state.key is None and (self._context.pending_work.is_staged_new(entity)
                                      or state.session is self._session.sync_session)

    def _drop_if_staged_new(self, entity: TEntity) -> bool:
        """A new, never saved entity: drop it from the unit of work (True); error if it was never staged."""
        if sa_inspect(entity).key is not None:
            return False
        if not self._is_staged_new(entity):
            raise ValueError(f"this {self._model.__name__} has never been saved; there is nothing to delete")
        self._context.pending_work.unstage(entity)
        if entity in self._session:
            self._session.expunge(entity)
        return True

    def _ensure_nothing_related_to_save(self, entity: TEntity) -> None:
        """An _async insert writes the entity's own row only: refuse related objects that would be lost."""
        state = sa_inspect(entity)
        for relationship in self._mapper.relationships:
            if relationship.key in self._many_to_one or relationship.key not in state.dict:
                continue  # many-to-one objects are written as foreign keys
            value = state.dict[relationship.key]
            if (relationship.uselist and len(value)) or (not relationship.uselist and value is not None):
                raise ValueError(f"'{relationship.key}' of this {self._model.__name__} holds related objects, "
                                 f"which an _async insert does not save; save them separately, or stage the "
                                 f"entity with add_single() and call save_changes_async()")

    def _track(self, entity: TEntity) -> TEntity:
        """The instance of this entity's row that the unit of work tracks (a detached entity is attached)."""
        state = sa_inspect(entity)
        if state.key is None:
            raise ValueError(f"this {self._model.__name__} has not been saved yet; use add_single or save")
        session = self._session
        sync = session.sync_session
        if state.session is not None:
            if state.session is not sync:
                raise ValueError(f"this {self._model.__name__} belongs to another session")
            return entity

        tracked = sync.identity_map.get(state.key)
        if tracked is None:
            _reconcile_graph(session, entity)
            session.add(entity)  # re-attach; its changes since loading are kept and written on save
            return entity

        # The unit of work already tracks this row: carry the detached entity's changes over to it.
        columns, scalars, collections = self._pending_changes(entity)
        copied = {**columns, **{name: self._resolve_related(target) for name, target in scalars.items()}}
        if copied:
            tracked_state = sa_inspect(tracked)
            originals = {name: _current_value(tracked_state, name) for name in copied}
            _assign([tracked], copied)
            self._context.pending_work.stage_update(tracked, copied, originals)
        for name, (added, removed) in collections.items():
            if name not in sa_inspect(tracked).dict:
                raise ValueError(f"cannot copy the changes of '{name}': it is not loaded on the {self._model.__name__} "
                                 f"this unit of work tracks; load it with includes=['{name}'] first")
            added_items = [self._resolve_related(item) for item in added]
            _change_collection(getattr(tracked, name), added_items,
                               [self._resolve_related(item) for item in removed])
            for item in added_items:
                if item not in session:
                    session.add(item)  # now part of a tracked entity: saved with the unit of work
        return cast(TEntity, tracked)

    def _resolve_related(self, related: Any) -> Any:
        """The object to reference from a tracked entity: the unit of work's instance of the same row if it
        has one, else the object itself (prepared to be attached)."""
        if related is None:
            return None
        session = self._session
        state = sa_inspect(related)
        if state.session is session.sync_session:
            return related
        if state.session is not None:
            raise ValueError(f"this {type(related).__name__} belongs to another session")
        if state.key is not None:
            tracked = session.sync_session.identity_map.get(state.key)
            if tracked is not None:
                return tracked
        _reconcile_graph(session, related)
        return related

    def _resolved_values(self, values: Values) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for name, value in values.items():
            relationship = self._mapper.relationships.get(name)
            if relationship is None:
                resolved[name] = value
            elif relationship.uselist:
                resolved[name] = [self._resolve_related(item) for item in value]
            else:
                resolved[name] = self._resolve_related(value)
        return resolved

    def _check_attribute_names(self, values: Values, *, columns_only: bool) -> None:
        mapped = self._mapper.column_attrs if columns_only else self._mapper.attrs
        for name in values:
            if name not in mapped:
                raise AttributeError(f"{self._model.__name__} has no {'column' if columns_only else 'mapped'} "
                                     f"attribute '{name}'")
            if name == self._primary_key_name:
                raise ValueError(f"the primary key '{name}' of {self._model.__name__} cannot be updated")

    def _criteria_update(self, args: tuple[Any, ...], values: Values | None) -> tuple[tuple[Any, ...], dict[str, Any]]:
        if not values:
            raise ValueError("an update by criteria needs values")
        criteria = _required_criteria(args, "update")
        self._check_attribute_names(values, columns_only=True)
        return criteria, dict(values)

    def _pending_changes(self, entity: TEntity) -> tuple[dict[str, Any], dict[str, Any],
                                                         dict[str, tuple[list[Any], list[Any]]]]:
        """Changes of an entity since it was loaded: (columns, single-object relationships, collections as
        (added, removed))."""
        state = sa_inspect(entity)
        columns: dict[str, Any] = {}
        scalars: dict[str, Any] = {}
        collections: dict[str, tuple[list[Any], list[Any]]] = {}
        for key in self._column_keys:
            added = list(state.attrs[key].history.added or ())
            if added:
                columns[key] = added[0]
        for relationship in self._mapper.relationships:
            history = state.attrs[relationship.key].history
            if not history.has_changes():
                continue
            if relationship.uselist:
                collections[relationship.key] = (list(history.added or ()), list(history.deleted or ()))
            else:
                added = list(history.added or ())
                scalars[relationship.key] = added[0] if added else None
        return columns, scalars, collections

    def _insert_values(self, entity: TEntity) -> dict[str, Any]:
        """Column values of a new entity, with foreign keys taken from its many-to-one related objects."""
        state = sa_inspect(entity)
        values = {key: state.dict[key] for key in self._column_keys if key in state.dict}
        for name, relationship in self._many_to_one.items():
            if state.dict.get(name) is None:
                continue
            for key, value in self._foreign_key_values(relationship, state.dict[name]).items():
                if values.get(key) is None:
                    values[key] = value
        return values

    def _values_of_new(self, entity: TEntity) -> dict[str, Any]:
        """The values a new entity with a primary key writes to the existing row with that key."""
        return {key: value for key, value in self._insert_values(entity).items() if key != self._primary_key_name}

    def _foreign_key_values(self, relationship: RelationshipProperty[Any], target: Any) -> dict[str, Any]:
        values: dict[str, Any] = {}
        target_state = sa_inspect(target) if target is not None else None
        for local_column, remote_column in relationship.local_remote_pairs or ():
            local_key = self._mapper.get_property_by_column(local_column).key
            if target_state is None:
                values[local_key] = None
                continue
            remote_key = relationship.mapper.get_property_by_column(remote_column).key
            remote_value = target_state.dict.get(remote_key)
            if remote_value is None:
                raise ValueError(f"the related {relationship.mapper.class_.__name__} has no {remote_key} yet; "
                                 f"save it first")
            values[local_key] = remote_value
        return values

    def _column_snapshot(self, row: Any) -> dict[str, Any]:
        row_dict = sa_inspect(row).dict
        return {key: row_dict.get(key) for key in self._column_keys}

    def _set_committed(self, entity: Any, snapshot: dict[str, Any], *, keep_changes: bool) -> None:
        state = sa_inspect(entity)
        for key, value in snapshot.items():
            if keep_changes and state.attrs[key].history.has_changes():
                continue  # a change staged in the unit of work wins until it is saved
            set_committed_value(entity, key, value)


# ==========================================================================================================
# Module helpers
# ==========================================================================================================

def _reconcile_graph(session: AsyncSession, root: Any) -> None:
    """Prepare a detached or new object graph to be attached to the session.

    Wherever the graph references a detached copy of a row the session already tracks, the reference is
    pointed at the tracked instance (keeping pending changes as changes), so that the save-update cascade
    does not try to attach a second instance of that row ("another instance with key is already present").
    """
    sync = session.sync_session

    def tracked_copy(entity: Any) -> Any:
        state = sa_inspect(entity)
        if state.session is None and state.key is not None:
            tracked = sync.identity_map.get(state.key)
            if tracked is not None:
                return tracked
        return entity

    seen: set[int] = set()
    stack = [root]
    while stack:
        entity = stack.pop()
        if id(entity) in seen:
            continue
        seen.add(id(entity))
        state = sa_inspect(entity)
        if state.session is not None:
            continue  # tracked already: its references are the session's own
        for relationship in state.mapper.relationships:
            key = relationship.key
            if key not in state.dict:
                continue
            history = state.attrs[key].history
            if relationship.uselist:
                current = list(state.dict[key] or ())
                swapped = [tracked_copy(item) for item in current]
                if any(new is not old for new, old in zip(swapped, current)):
                    if history.has_changes():
                        set_committed_value(entity, key, [tracked_copy(item) for item in history.non_added()])
                        _change_collection(getattr(entity, key), [tracked_copy(item) for item in history.added],
                                           [tracked_copy(item) for item in history.deleted])
                    else:
                        set_committed_value(entity, key, swapped)
                stack.extend(swapped)
            else:
                value = state.dict[key]
                if value is None:
                    continue
                tracked = tracked_copy(value)
                if tracked is not value:
                    # Swapped without attribute events: an assignment would also append the entity to the tracked
                    # object's collection through the backref, and an object that gets into a collection that way
                    # is not cascaded into the session.
                    set_committed_value(entity, key, tracked)
                    if history.has_changes():
                        flag_modified(entity, key)  # still a pending change, written on save
                stack.append(tracked)


def _change_collection(collection: Any, added: list[Any], removed: list[Any]) -> None:
    for item in removed:
        if item in collection:
            collection.remove(item)
    for item in added:
        if item not in collection:
            collection.append(item)


def _revert(session: AsyncSession, entry: _Entry) -> None:
    """Take back the values a staged update applied when it was called (newest entry first)."""
    for key, original in reversed(list(entry.originals.items())):
        if original is _UNLOADED:
            session.sync_session.expire(entry.entity, [key])
        else:
            setattr(entry.entity, key, original)


def _current_value(state: Any, key: str) -> Any:
    if key not in state.dict:
        return _UNLOADED
    value = state.dict[key]
    relationship = state.mapper.relationships.get(key)
    if relationship is not None and relationship.uselist:
        return list(value)
    return value


async def _reload_expired_async(session: AsyncSession, entities: Iterable[Any], batch_size: int) -> None:
    """Reload the columns the ORM expired at flush (SQL-expression values, database-side defaults), one query
    per entity type and batch. Only those columns are set; loaded relationships and other columns stay."""
    groups: dict[Any, list[tuple[Any, list[str]]]] = {}
    for entity in entities:
        state = sa_inspect(entity)
        if state.key is None:
            continue
        expired = [prop.key for prop in state.mapper.column_attrs if prop.key in state.expired_attributes]
        if expired:
            groups.setdefault(state.mapper, []).append((entity, expired))

    for mapper, items in groups.items():
        keys = [prop.key for prop in mapper.column_attrs]
        primary_key_name = mapper.get_property_by_column(mapper.primary_key[0]).key
        primary_key = getattr(mapper.class_, primary_key_name)
        key_position = keys.index(primary_key_name)
        columns = [getattr(mapper.class_, key) for key in keys]
        for chunk in _chunks(items, batch_size):
            ids = [_primary_key_value(entity) for entity, _ in chunk]
            result = await session.execute(select(*columns).where(primary_key.in_(ids)))
            fresh = {row[key_position]: row for row in result.all()}
            for entity, expired in chunk:
                row = fresh.get(_primary_key_value(entity))
                if row is None:
                    continue
                for key in expired:
                    set_committed_value(entity, key, row[keys.index(key)])


def _tracked_keys(session: AsyncSession) -> frozenset[IdentityKey]:
    return frozenset(session.sync_session.identity_map.keys())


def _loader_for_path(path: list[QueryableAttribute[Any]]) -> LoaderOption:
    """Chain loaders along a relationship path: selectinload for collections, joinedload for single objects."""
    loader: Any = None
    for attribute in path:
        is_collection = bool(attribute.property.uselist)
        if loader is None:
            loader = selectinload(attribute) if is_collection else joinedload(attribute)
        else:
            loader = loader.selectinload(attribute) if is_collection else loader.joinedload(attribute)
    return cast(LoaderOption, loader)


def _identity_key(entity: Any) -> IdentityKey:
    key = sa_inspect(entity).key
    if key is None:
        raise ValueError(f"this {type(entity).__name__} has not been saved yet")
    return cast(IdentityKey, key)


def _primary_key_value(entity: Any) -> Any:
    return _identity_key(entity)[1][0]


def _assign(entities: Iterable[Any], values: dict[str, Any]) -> None:
    for entity in entities:
        for name, value in values.items():
            setattr(entity, name, value)


def _chunks(items: Sequence[_T], size: int) -> Iterator[list[_T]]:
    for start in range(0, len(items), size):
        yield list(items[start:start + size])


def _validate_criteria(criteria: Sequence[Any]) -> None:
    for criterion in criteria:
        if isinstance(criterion, Select):
            raise TypeError("a statement cannot be combined with other criteria")
        if not isinstance(criterion, ColumnElement):
            # e.g. a Python bool from `Account.Id is x`, which SQLAlchemy would turn into an always-true filter
            raise TypeError(f"criteria must be SQL expressions such as Account.Id == account_id, "
                            f"got {criterion!r}")


def _is_criteria_form(args: tuple[Any, ...], values: Values | None) -> bool:
    """update_range / delete_range: SQL criteria rather than an iterable of entities."""
    if not args:
        return values is not None  # values without criteria: refused by _required_criteria
    return isinstance(args[0], ColumnElement)


def _required_criteria(args: tuple[Any, ...], operation: str) -> tuple[Any, ...]:
    if not args:
        raise ValueError(f"an {operation} by criteria needs at least one criterion "
                         f"(refusing to {operation} every row)")
    _validate_criteria(args)
    return args


def _single_iterable(args: tuple[Any, ...]) -> Iterable[Any]:
    if len(args) != 1 or isinstance(args[0], (str, bytes)) or not isinstance(args[0], Iterable):
        raise TypeError("expected one iterable of entities, or SQL criteria")
    return cast(Iterable[Any], args[0])


def _as_sequence(value: Sequence[Any] | Any) -> Sequence[Any]:
    if isinstance(value, (ColumnElement, QueryableAttribute)):
        return (value,)  # a single ordering term given without a list
    return tuple(value)


def _non_negative(name: str, value: int) -> int:
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value
