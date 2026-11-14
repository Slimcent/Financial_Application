# Design Decisions

## Project Structure

The project follows a layered structure, separating application logic, services, models and database access.

Existing application and processing classes remain in place. Services, repositories, models and utilities have been moved into their respective packages, with imports updated accordingly.

## SQLAlchemy

SQLAlchemy 2.x typed mappings are used for entity definitions.

Relationships, foreign keys and shared column types are defined explicitly to keep database mappings consistent.

## Entity Identifiers

UUID identifiers are used for major entities. Integer identifiers are retained for smaller lookup tables where suitable.

## Audit Fields

Common entity properties are defined in the base entity. Audit fields include creation and modification timestamps, with nullable references for the users responsible for those operations.

## Migrations

Alembic configuration and migration files are maintained under `Data/Migrations`.

Revision `79366144bc84` replaces the previous migration history and serves as the initial schema for new databases.

Existing databases using older revisions require separate handling. The new baseline is not intended as an automatic upgrade path.

## Interfaces

`Data/Interfaces` holds the repository and unit of work contracts; `Data/Implementations` holds their SQLAlchemy implementations. `Services/Interfaces` is reserved for service interfaces, which will be introduced as services are developed.

## Generic Repository

A single generic repository, `Repository[TEntity]`, is used for every entity instead of separate data access code per entity, so database access has one consistent implementation. Existing services will be moved to it step by step.

- **Naming.** Operations are grouped into add, update, delete, get and save, with `_single` and `_range` forms. Only methods ending in `_async` are awaited.
- **Staged and persisted operations.** An operation without the suffix only stages a change; an `_async` operation writes its own data at once, in its own transaction.
- **Queries.** Filters are SQLAlchemy expressions. Related objects are loaded explicitly with includes, because relationships never load implicitly (`raise_on_sql`).
- **`get_single_async`** requires a filter and fails when more than one row matches, instead of returning the first row.
- **Bulk operations** load the matching rows and change them through the ORM, so entity events and defaults apply. Rows are processed in batches (500 by default) to limit memory use.
- **Row locks.** A `for_update` read refreshes an entity already in memory with the locked values and keeps its staged changes.

## Unit of Work

`UnitofWork` owns one session for a business operation and gives access to the repositories of every entity.

- Staged changes are written only by `save_changes_async()`, in one transaction and in the order the operations were called.
- `_async` operations run on the unit of work's own session. Staged changes are set aside while they run, so only the operation's data is committed and it never waits on row locks held by the unit of work.
- After a rollback or a failed save, entities keep the values they were loaded with and can still be read.
- When the `async with` block ends, the session is closed (or invalidated if closing fails), and the repositories of that unit of work stop working.