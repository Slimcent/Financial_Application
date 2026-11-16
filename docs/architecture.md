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
└── Seed/

Services/
├── Exceptions/
├── Extensions/
├── Handler/
├── Implementations/
└── Interfaces/

Infrastructure/
├── DependencyInjection/
├── Logging/
└── Security.py

tests/
├── unit/
└── integration/

docs/
```

## Application Layers

**Application** contains the account, account type, customer, staff and transaction application classes. `ApplicationProcessing` handles supporting processing operations. Both receive their dependencies through their constructors and call the services; they do not access the database themselves.

**Services** contains the business logic for accounts, account types, customers, staff, users and transactions. Every service implements an interface from `Services/Interfaces` and works on the database only through the unit of work it is given.

**Data** manages the database connection, the generic repository and unit of work, lookup seeding and migrations.

**Models** contains SQLAlchemy entities, request and response models, constants and pagination types.

**Infrastructure** contains the composition root (dependency injection), logging and password hashing.

**Api** provides directories for future API routers and dependencies.

`Data/Interfaces` contains the repository and unit of work contracts. `Services/Interfaces` contains the service contracts.

```text
main.py → Application / ApplicationProcessing → Services (interfaces) → Unit of Work → Repository → SQLAlchemy → MySQL
```

## Dependency Injection

`Infrastructure/DependencyInjection/container.py` (`Container`) is the composition root. It creates the database once and the services once, and creates a new unit of work for every operation (`create_unit_of_work()`, a `UnitOfWorkFactory`).

Services hold no state and no database session. The caller owns the unit of work: it enters it, passes it to every service call and decides where a business operation starts and ends — the shape an API request dependency will have.

```python
container = Container()

async with container.create_unit_of_work() as unit_of_work:
    account = await container.account_service.get_account_details_by_account_number(unit_of_work, "2600000001")
```

`main.py` builds the container, seeds missing lookup rows, wires the application classes with the factory and the services, and disposes of the database at the end.

## Service Layer

| Contract | Implementation | Purpose |
| --- | --- | --- |
| `IUserService` | `UserService` | Users shared by staff and customers; building blocks (`stage_*`, `ensure_*`) for the other services |
| `IStaffService` | `StaffService` | Staff members and their users |
| `ICustomerService` | `CustomerService` | Customers, their users and accounts; opening, closing and deactivating accounts |
| `IAccountTypeService` | `AccountTypeService` | Account types |
| `IAccountService` | `AccountService` | Reading accounts and balances |
| `ITransactionService` | `TransactionService` | Funding, transfers and transaction history |

Every operation takes the caller's unit of work as its first argument. Operations that change data stage their changes and save them with one `save_changes_async()` before they return, so related rows (a user and its customer record, both sides of a transfer) are saved together or not at all.

- **Money.** Funding and transfers lock the account rows (`for_update`) before the balance changes; a transfer locks both accounts in one query, in primary-key order. The debit and the credit of a transfer share a `TransferReference`. Amounts and balances are `Decimal`.
- **Active accounts.** An account can only be funded, send or receive money while both the account and its owner are active. A deactivated customer cannot open accounts.
- **Queries.** Filtering, searching and paging run in the database. The non-paginated transaction list returns the 15 most recent matching transactions.
- **Helpers.** `Services/Extensions` holds the error translation (`exception_handler.py`) and the entity-to-response mapping (`response_mappers.py`); `Services/Handler/AccountNumber.py` generates account numbers.

## Error Handling

Services raise the domain errors in `Services/Exceptions`, all derived from `ServiceError`; the unit of work then rolls back.

| Error | Meaning |
| --- | --- |
| `NotFoundError` | The record does not exist |
| `ConflictError` | A value is already in use |
| `DeleteRestrictedError` | Other records depend on the record (a `ConflictError`) |
| `BusinessRuleError` | A business rule forbids the operation |
| `InsufficientFundsError` | The balance does not cover the amount (a `BusinessRuleError`) |
| `InvalidInputError` | A value passed to a service is not valid |
| `PersistenceError` | The database refused the changes for another reason |

When the database refuses a save, `exception_handler.py` reads the kind of violation (MySQL error number, PostgreSQL SQLSTATE or SQLite message) and the constraint name, and raises the matching error: a unique violation is a conflict, a foreign key violation is a restricted delete or a missing record, a check violation is a business rule, anything else a persistence error.

Error messages never contain email addresses or account numbers.

## Responses

Response models (`Models/Dtos/Response`) are pydantic models derived from `BaseResponse`; unknown fields are rejected. Identifiers have the type of their key column (`GuidId`, `IntegerId`: strict); money fields are `Decimal` (`Money`) and also accept floats, converted exactly. Accounts show whether they are active, and account responses whether their holder is.

## Password Hashing

`Infrastructure/Security.py` hashes passwords with bcrypt. The cost is set by `BCRYPT_ROUNDS` (4 to 31, default 12). The services use the `*_async` functions, which run bcrypt in a worker thread so the event loop is not blocked.

## Database

SQLAlchemy 2.x is used for ORM mappings and database operations. Entity definitions use typed columns, relationships and foreign key constraints.

Major entities use UUID identifiers, while lookup entities retain integer identifiers where appropriate. Common entity fields are defined in `Models/Entities/base_entity.py`.

Alembic migrations are stored in `Data/Migrations`. Revision `79366144bc84` defines the initial schema for fresh database installations; revision `87878a138824` adds `Accounts.Active`.

The lookup rows (roles, account types, transaction types, modes and statuses) use the identifiers in `Models/Constants/AppConstants.py`. `Data/Seed/lookup_seed.py` adds the rows that are missing when the application starts — all of them on the first run — and stops with a `LookupSeedError` when the lookup data contradicts the constants.

## Data Access

The generic repository and the unit of work are the data access layer for all entities.

| Contract | Implementation | Purpose |
| --- | --- | --- |
| `Data/Interfaces/i_repository.py` — `IRepository[TEntity]` | `Data/Implementations/repository.py` — `Repository` | CRUD operations and queries for one entity type |
| `Data/Interfaces/i_unit_of_work.py` — `IUnitOfWork` | `Data/Implementations/unit_of_work.py` — `UnitOfWork` | One session for a business operation, repositories for every entity, saving staged changes |

**Repository.** Operations are named add, update, delete, get and save, in `_single` and `_range` forms. Operations without a suffix stage a change; operations ending in `_async` are awaited and persist their own data at once. Queries accept filters, includes, ordering, skip / take, paging and row locking. `count_async`, `sum_async` and `exists_async` accept criteria or a statement built from `query()`.

**Unit of Work.** Used with `async with`. It creates the repositories (for example `unit_of_work.accounts`), persists all staged changes in one transaction with `save_changes_async()`, discards them with `rollback_async()`, and closes its session when the block ends.

```python
async with UnitOfWork() as unit_of_work:
    account = await unit_of_work.accounts.get_single_async(Account.AccountNumber == account_number, for_update=True)
    unit_of_work.accounts.update_single(account, {"Balance": account.Balance + amount})
    unit_of_work.transactions.add_single(transaction)
    await unit_of_work.save_changes_async()  # one commit for both changes
```

The services use the staged operations and one `save_changes_async()` per operation; the `_async` write operations commit at once and would release the row locks of the unit of work.

## Testing

Tests are separated into unit and integration suites.

Unit tests cover request and response validation, entity mappings, relationships, column types, migration definitions, the repository and unit of work, lookup seeding, the services, their helpers, password hashing and the composition root. The repository, unit of work, seeding and service tests (`tests/unit/Data`, `tests/unit/Services`) run on an in-memory SQLite database. Integration tests cover database-related functionality and are maintained separately.
