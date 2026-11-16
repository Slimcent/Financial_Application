# Change Log

## 2026-11-15

Details: [003 — Service Layer](003-service-layer.md).

### Services

- Moved every service to the generic repository and the unit of work; the caller passes the unit of work into every call.
- Added service interfaces (`Services/Interfaces`) and a composition root (`Infrastructure/DependencyInjection`).
- Added domain errors (`Services/Exceptions`); services raise them instead of returning `None` or `False`.
- Database refusals are translated by kind: only unique violations are conflicts. Error messages no longer contain email addresses or account numbers.
- Funding and transfers lock the accounts, check that accounts and owners are active, and record transfers with a shared reference. Filtering and paging run in the database.
- Added closing accounts and deactivating customers (user and accounts); a deactivated customer cannot open accounts.
- Password hashing cost is configurable (`BCRYPT_ROUNDS`) and hashing runs off the event loop.

### Data Access

- Removed the raw SQL connection pool, the SQL query files and the account and transaction repositories.
- Renamed `IUnitofWork` / `UnitofWork` to `IUnitOfWork` / `UnitOfWork`; added `UnitOfWorkFactory`.
- `sum_async` accepts a statement built from `query()`.

### Database

- Added `Accounts.Active` (revision `87878a138824`).
- Added lookup seeding (`Data/Seed`): missing rows are added at start-up; contradicting lookup data is reported.
- Corrected `AppConstants.WithdrawalTransactionTypeId` (3).

### Models

- Converted the response models to pydantic (`BaseResponse`): strict identifiers, `Decimal` money (floats accepted), `active` on accounts and account holders.
- Added an optional description to `FundAccountRequest`.

### Application

- Application and processing classes receive the unit of work factory and the services through their constructors.

### Testing

- Added response, service, error handling, mapping, seeding, password hashing and composition root tests, and tests for revision `87878a138824`.
- Adapted the migration tests to the revision chain and the entity tests to `Accounts.Active`.
- Added `aiosqlite` to `requirements.txt`.
- Verified all 2,663 unit tests locally with SQLAlchemy 2.1.

## 2026-11-13

Details: [002 — Generic Repository and Unit of Work](002-generic-repository.md).

### Data Access

- Added the generic repository (`IRepository`, `Repository`) and the unit of work (`IUnitofWork`, `UnitofWork`).
- Staged operations are persisted together by the unit of work; `_async` operations persist at once.
- Bulk updates and deletes go through the ORM and run in batches.
- The unit of work closes its session when its block ends.

### Testing

- Added `pytest-asyncio` and set `asyncio_default_fixture_loop_scope` in `pytest.ini`.
- Added 309 repository and unit of work tests, run on SQLite in memory.
- Fixed an issue found by the tests where new related objects could be left unsaved.
- Verified all 1,626 unit tests locally.

## 2026-11-12

### Project Structure

- Reorganised models, services, repositories and utilities into separate packages.
- Updated imports across the existing application and processing classes.
- Added directories for API components, service interfaces and repository interfaces.
- Separated unit and integration tests.

### Database

- Updated entity mappings to SQLAlchemy 2.x conventions.
- Added UUID identifiers for major entities.
- Updated relationships, foreign key constraints and shared audit fields.
- Moved database connections and SQL queries into `Data`.
- Replaced the previous migration history with initial revision `79366144bc84`.

### Testing

- Added unit tests for entity mappings, relationships, column types and migrations.
- Retained and relocated the existing request validation tests.
- Verified all 1,317 unit tests locally.
- Confirmed application, processing and service module imports.
- Verified the Alembic migration head.

Database migrations and end-to-end workflows have not yet been tested against a fresh database.