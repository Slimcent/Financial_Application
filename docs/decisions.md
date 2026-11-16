# Design Decisions

## Project Structure

The project follows a layered structure, separating application logic, services, models and database access.

Existing application and processing classes remain in place. Services, repositories, models and utilities have been moved into their respective packages, with imports updated accordingly.

The previous data access code — the raw SQL connection pool (`Data/database_connection.py`), the SQL query files (`Data/SqlQueries`) and the account and transaction repositories — has been removed. All database access goes through the generic repository and the unit of work.

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

Schema changes after the baseline are new revisions on top of it, never edits of an applied revision. Revision `87878a138824` adds `Accounts.Active` (existing accounts stay active). The migration tests check that the schema after `alembic upgrade head` is exactly the schema of the entities.

## Interfaces

`Data/Interfaces` holds the repository and unit of work contracts; `Data/Implementations` holds their SQLAlchemy implementations. `Services/Interfaces` holds the service contracts (`IUserService`, `IStaffService`, `ICustomerService`, `IAccountTypeService`, `IAccountService`, `ITransactionService`); `Services/Implementations` holds the services that implement them. Interfaces carry the `I` prefix, implementations the same name without it.

## Generic Repository

A single generic repository, `Repository[TEntity]`, is used for every entity instead of separate data access code per entity, so database access has one consistent implementation. Every service uses it.

- **Naming.** Operations are grouped into add, update, delete, get and save, with `_single` and `_range` forms. Only methods ending in `_async` are awaited.
- **Staged and persisted operations.** An operation without the suffix only stages a change; an `_async` operation writes its own data at once, in its own transaction.
- **Queries.** Filters are SQLAlchemy expressions. Related objects are loaded explicitly with includes, because relationships never load implicitly (`raise_on_sql`).
- **`get_single_async`** requires a filter and fails when more than one row matches, instead of returning the first row.
- **Aggregates.** `count_async`, `sum_async` and `exists_async` accept criteria or a statement built from `query()`, so they can work across joins.
- **Bulk operations** load the matching rows and change them through the ORM, so entity events and defaults apply. Rows are processed in batches (500 by default) to limit memory use.
- **Row locks.** A `for_update` read refreshes an entity already in memory with the locked values and keeps its staged changes.

## Unit of Work

`UnitOfWork` (contract `IUnitOfWork`, named like its folder) owns one session for a business operation and gives access to the repositories of every entity.

- Staged changes are written only by `save_changes_async()`, in one transaction and in the order the operations were called.
- `_async` operations run on the unit of work's own session. Staged changes are set aside while they run, so only the operation's data is committed and it never waits on row locks held by the unit of work.
- After a rollback or a failed save, entities keep the values they were loaded with and can still be read.
- When the `async with` block ends, the session is closed (or invalidated if closing fails), and the repositories of that unit of work stop working.

## Service Layer

Services contain the business rules and use only the unit of work they are given; they hold no session and no state, so one instance of each serves every caller.

- **Unit of work from the caller.** Every operation takes an active unit of work as its first argument. The caller creates it (from the container's factory), enters it and passes it on, like a request-scoped dependency of an API.
- **One save per operation.** An operation that changes data stages its changes and calls `save_changes_async()` once, so everything it changes is saved in one transaction. The `_async` write operations of the repository are not used by services: they commit at once and would release row locks.
- **Composition.** Services that build on each other share the caller's unit of work: the staff and customer services use the `stage_*` and `ensure_*` operations of the user service, which check and stage but do not save.
- **Locking.** Funding and transfers read the accounts with `for_update`; a transfer locks both accounts in one query ordered by primary key, so concurrent transfers cannot deadlock each other.

## Dependency Injection

`Infrastructure/DependencyInjection/container.py` is the single composition root: it creates the database and the services and hands out units of work. Application classes receive the unit of work factory and the service interfaces through their constructors; nothing creates its own database connection.

## Error Handling

Services raise domain errors (`Services/Exceptions`) instead of returning `None` or `False`.

- Only a unique key violation is a conflict. A foreign key violation is a restricted delete (when deleting) or a missing record; a check constraint violation is a business rule; any other refusal is a `PersistenceError`. A value the database cannot store is an `InvalidInputError`.
- The kind of violation is read from each database's own signal (MySQL error number, PostgreSQL SQLSTATE, SQLite message), and the constraint name from the error, so particular constraints can have their own message (for example an email address in use).
- A generated account number taken by another operation between the check and the save is retried with a new number (up to three saves).
- Error messages describe the problem without personal or account data: no email addresses, no account numbers.

## Responses

Responses are pydantic models with a shared base (`BaseResponse`) that rejects unknown fields.

- Identifiers have exactly the type of their key column: `GuidId` (a UUID; from JSON, its text form) and `IntegerId` (an int; not a bool, float or text).
- Money fields are `Decimal`, as the entities store money. They also accept floats, taken by their shortest text form, so a float gains no binary rounding digits.
- Accounts show whether they are active (`AccountsResponse.active`); account responses show whether their holder is (`AccountResponse.active`).

## Account Deactivation and Closing

Customers with accounts or transactions cannot be deleted. Instead, deactivating a customer deactivates the customer's user and every account (in one transaction); balances and history are kept. Inactive accounts cannot be funded, send or receive transfers, and a deactivated customer cannot open accounts. An account with a zero balance and no transactions can be closed (deleted); a customer whose accounts are all closed can be deleted.

## Lookup Seeding

The services refer to lookup rows by the identifiers in `AppConstants`, so the seed inserts exactly those identifiers. At start-up the application checks that every required lookup row exists (one count per table) and adds only the missing ones — all of them on the first run, none on later runs. Existing rows are never changed. Lookup data that contradicts the constants (a required name held by another identifier) stops the start-up with a `LookupSeedError` that lists the rows to correct, instead of being ignored.

## Password Hashing

Passwords are hashed with bcrypt, which is slow on purpose. The cost is configurable (`BCRYPT_ROUNDS`, default 12); tests use the lowest cost. Hashing runs in a worker thread, so a hash does not block the other requests on the event loop.
