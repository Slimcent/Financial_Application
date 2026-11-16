# 003 — Service Layer

## Summary

Moved every service to the generic repository and the unit of work (see [002](002-generic-repository.md)). Services implement interfaces, receive the caller's unit of work in every call, raise domain errors and return pydantic responses. The previous data access code has been removed. The application and processing classes are wired through a composition root.

## Added

- `Services/Interfaces` — `IUserService`, `IStaffService`, `ICustomerService`, `IAccountTypeService`, `IAccountService`, `ITransactionService`.
- `Services/Exceptions/domain_exceptions.py` — `ServiceError` and the domain errors.
- `Services/Extensions/response_mappers.py` — entity to response mapping and the includes the mappers need.
- `Infrastructure/DependencyInjection/container.py` — `Container`, the composition root.
- `Data/Seed/lookup_seed.py` — lookup seeding (`python -m Data.Seed.lookup_seed` to run it on its own).
- `Data/Migrations/versions/87878a138824_add_account_active.py` — `Accounts.Active`.
- `Models/Dtos/Response/base_response.py` — `BaseResponse`, `GuidId`, `IntegerId`, `Money`.
- `UnitOfWorkFactory` in `Data/Interfaces/i_unit_of_work.py`.

## Changed

- Services: rewritten on the unit of work (`Services/Implementations`).
- `Services/Extensions/exception_handler.py` — translation of database refusals into domain errors; validation of single values with the request field types.
- `Services/Handler/AccountNumber.py` — synchronous, uses `secrets`; uniqueness is checked by the customer service.
- `Infrastructure/Security.py` — configurable bcrypt cost (`BCRYPT_ROUNDS`), `hash_password_async` / `verify_password_async`.
- `Models/Dtos/Response` — pydantic models.
- `Models/Dtos/Request/fund_account_request.py` — optional `description`.
- `Models/Constants/AppConstants.py` — `WithdrawalTransactionTypeId` is 3.
- `Models/Entities/accounts.py` — `Active`.
- `IUnitofWork` / `UnitofWork` renamed to `IUnitOfWork` / `UnitOfWork`; `sum_async` accepts a statement.
- `Application`, `ApplicationProcessing`, `main.py` — dependencies passed through constructors.

## Removed

- `Data/database_connection.py`, `Data/SqlQueries`, `Data/Implementations/account_repository.py`, `Data/Implementations/transaction_repository.py`.
- `Services/Extensions/transaction_validation.py` (unused, hard-coded identifiers).
- `tests/integration/Data/database_connection_test.py` (tested the removed connection pool).

## Operations

| Service | Operations |
| --- | --- |
| `IUserService` | `create_user`, `toggle_user_active_status`, `update_user`, `delete_user`; building blocks `stage_new_user`, `stage_user_update`, `ensure_user_can_be_deleted` |
| `IStaffService` | `create_staff`, `get_all_staff`, `get_staff_by_id`, `toggle_staff_active_status`, `update_staff`, `delete_staff` |
| `ICustomerService` | `create_customer`, `update_customer`, `delete_customer`, `deactivate_customer_account`, `get_all_customers`, `get_customer_by_id`, `open_account`, `close_account` |
| `IAccountTypeService` | `get_all_account_types`, `get_account_type_by_id`, `add_account_type`, `update_account_type`, `delete_account_type` |
| `IAccountService` | `get_all_customer_accounts`, `get_customer_account_details`, `get_customer_accounts_with_user_id`, `get_account_details_by_account_number` |
| `ITransactionService` | `fund_account`, `transfer_funds`, `get_user_transactions`, `filter_user_transactions`, `get_all_transactions_paginated`, `get_all_transactions_non_paginated` |

- Every operation takes the caller's active unit of work first; operations that change data save once, in one transaction.
- `fund_account` takes a `FundAccountRequest`: a deposit (credit) into an active account of an active customer.
- `transfer_funds` locks both accounts in primary-key order, checks both accounts and owners are active and the balance covers the amount, and records a debit and a credit sharing one `TransferReference`.
- `get_all_transactions_paginated` pages in the database; `get_all_transactions_non_paginated` returns the 15 most recent matching transactions.
- `deactivate_customer_account` deactivates the customer's user and accounts; `close_account` deletes an account with a zero balance and no transactions; `open_account` refuses a deactivated customer.
- Deleting a user, staff member or customer with accounts or transactions raises `DeleteRestrictedError`.

## Error Handling

| Database refusal | Domain error |
| --- | --- |
| Unique violation | `ConflictError` (message per constraint where known) |
| Foreign key violation, when deleting | `DeleteRestrictedError` |
| Foreign key violation, otherwise | `NotFoundError` |
| Check violation | `BusinessRuleError` (message per check constraint) |
| Not null violation, anything else | `PersistenceError` |
| Value the database cannot store | `InvalidInputError` |

- The kind is read from the MySQL error number, the PostgreSQL SQLSTATE or the SQLite message; the constraint name from the error (for SQLite unique constraints, derived from the columns with the naming convention).
- A generated account number taken between the check and the save is retried with a new number, up to three saves.
- Messages never contain email addresses or account numbers.

## Fixes Found by Testing

- A staff list and a customer list joined `Users` twice (once for sorting, once for loading). They now join once for sorting and load the related rows with separate `SELECT ... IN` queries.
- Hashing every test user at the production bcrypt cost made the service tests take about 35 seconds. The cost is now configurable and the tests use the lowest cost; hashing also moved off the event loop.
- SQLite reports a foreign key violation of a delete with a trigger error code; violations are classified by the message for SQLite.

## Testing

- Added tests in `tests/unit/Models/Dtos/Response` (one file per response), `tests/unit/Services` (one file per service, plus `Extensions`, `Handler` and `Exceptions`), `tests/unit/Infrastructure` (composition root, password hashing), `tests/unit/Data/Seed` and `tests/unit/Data/Migrations` (revision `87878a138824`).
- The service tests run on the isolated SQLite test database of the repository tests (a fresh copy per test), with mocks for dependency injection and interaction tests. They cover success and failure of every operation, one save per operation, nothing saved on failure (a failing database trigger proves all-or-nothing saves), requested row locks, the SQL of the list queries and the messages' lack of personal data.
- The migration tests compare the schema after `alembic upgrade head` with the entities.
- Verified all 2,663 unit tests locally with SQLAlchemy 2.1.

## Open Points

- SQLite ignores row locks: the tests verify that the services request them, not how MySQL honours them. Concurrency needs MySQL integration tests.
- The application classes log service errors and return `None`; some of their own log messages contain email addresses and account numbers. `TransactionApplication` does not show the new `active` fields in its dictionaries.
- There is no operation to reactivate a deactivated customer's accounts.
- Response fields set after construction are not validated (`validate_assignment` is off).
- Deposits record the account owner as the sender.
- `get_customer_account_details` also returns accounts of staff members, while `get_all_customer_accounts` lists customers only.
- `AuthenticationService` still uses the removed connection pool and will be replaced by proper authentication.
- `Data/database_orm_async.py` logs every SQL statement (`echo=True`) and does not escape the database password in the URL.
