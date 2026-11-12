# Architecture

Financial Application is a Python banking application organised into separate layers for application logic, business services, data access and shared models.

## Project Structure

```text
Api/
├── Dependencies/
└── Router/

Application/
ApplicationProcessing/

Models/
├── Constants/
├── Dtos/
│   ├── Request/
│   └── Response/
├── Entities/
├── Enums/
└── Pagination/

Data/
├── Extensions/
├── Implementations/
├── Interfaces/
├── Migrations/
├── MockData/
├── Seed/
└── SqlQueries/

Services/
├── Extensions/
├── Handler/
├── Implementations/
└── Interfaces/

Infrastructure/
├── Logging/
└── Security.py

tests/
├── unit/
└── integration/

docs/
```

## Application Layers

**Application** contains the existing account, customer, staff and transaction application classes. `ApplicationProcessing` handles supporting processing operations.

**Services** contains the business logic for account management, authentication, customers, staff, users and transactions.

**Data** manages database connections, repository implementations, SQL queries and migrations.

**Models** contains SQLAlchemy entities, request and response models, constants and pagination types.

**Infrastructure** contains logging and security utilities.

**Api** provides directories for future API routers and dependencies.

The `Interfaces` directories are currently reserved for later development.

## Database

SQLAlchemy 2.x is used for ORM mappings and database operations. Entity definitions use typed columns, relationships and foreign key constraints.

Major entities use UUID identifiers, while lookup entities retain integer identifiers where appropriate. Common entity fields are defined in `Models/Entities/base_entity.py`.

Alembic migrations are stored in `Data/Migrations`. Revision `79366144bc84` defines the initial schema for fresh database installations.

## Testing

Tests are separated into unit and integration suites.

Unit tests cover request validation, entity mappings, relationships, column types and migration definitions. Integration tests cover database-related functionality and are maintained separately.