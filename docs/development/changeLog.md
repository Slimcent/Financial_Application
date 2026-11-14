# Change Log

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