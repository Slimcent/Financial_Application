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

**Data** manages database connections, the generic repository and unit of work, SQL queries and migrations.

**Models** contains SQLAlchemy entities, request and response models, constants and pagination types.

**Infrastructure** contains logging and security utilities.

**Api** provides directories for future API routers and dependencies.

`Data/Interfaces` contains the repository and unit of work contracts. `Services/Interfaces` is reserved for later development.

## Database

SQLAlchemy 2.x is used for ORM mappings and database operations. Entity definitions use typed columns, relationships and foreign key constraints.

Major entities use UUID identifiers, while lookup entities retain integer identifiers where appropriate. Common entity fields are defined in `Models/Entities/base_entity.py`.

Alembic migrations are stored in `Data/Migrations`. Revision `79366144bc84` defines the initial schema for fresh database installations.

## Data Access

The generic repository and the unit of work are the data access layer for all entities.

| Contract | Implementation | Purpose |
| --- | --- | --- |
| `Data/Interfaces/i_repository.py` — `IRepository[TEntity]` | `Data/Implementations/repository.py` — `Repository` | CRUD operations and queries for one entity type |
| `Data/Interfaces/i_unit_of_work.py` — `IUnitofWork` | `Data/Implementations/unit_of_work.py` — `UnitofWork` | One session for a business operation, repositories for every entity, saving staged changes |

**Repository.** Operations are named add, update, delete, get and save, in `_single` and `_range` forms. Operations without a suffix stage a change; operations ending in `_async` are awaited and persist their own data at once. Queries accept filters, includes, ordering, skip / take, paging and row locking.

**Unit of Work.** Used with `async with`. It creates the repositories (for example `unit_of_work.accounts`), persists all staged changes in one transaction with `save_changes_async()`, discards them with `rollback_async()`, and closes its session when the block ends.

```python
async with UnitofWork() as unit_of_work:
    account = await unit_of_work.accounts.get_single_async(Account.AccountNumber == account_number)
    unit_of_work.accounts.update_single(account, {"Balance": account.Balance + amount})
    unit_of_work.transactions.add_single(transaction)
    await unit_of_work.save_changes_async()  # one commit for both changes
```

Existing services still use the previous data access code and will be moved to the repository step by step.

## Testing

Tests are separated into unit and integration suites.

Unit tests cover request validation, entity mappings, relationships, column types and migration definitions. The repository and unit of work tests (`tests/unit/Data/Repository`, `tests/unit/Data/UnitOfWork`) run on an in-memory SQLite database. Integration tests cover database-related functionality and are maintained separately.