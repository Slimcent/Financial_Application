# Change Log

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