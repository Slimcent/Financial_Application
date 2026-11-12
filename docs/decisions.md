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

`Data/Interfaces` and `Services/Interfaces` have been created as part of the project structure. Repository and service interfaces will be introduced as the relevant components are developed.