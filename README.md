# Financial Application

Financial Application is a Python-based banking application that demonstrates the implementation of common banking operations using a layered backend architecture, asynchronous database access, SQLAlchemy and MySQL.

The project separates application workflows, business logic, persistence, models, DTOs, infrastructure and utility components to keep responsibilities organized and maintainable.

## Features

### Customer and User Management

* Customer management
* Staff management
* User management
* Account ownership and customer relationships
* Active account and user validation
* Customer deactivation (the customer and all of the customer's accounts)
* Deleting users, customers and staff only when they have no accounts or transactions

### Account Management

* Create and manage customer accounts
* Support different account types
* Open and close accounts
* Retrieve accounts by user
* Retrieve account details by account number
* Track individual account balances and whether each account is active
* Calculate total balances across customer accounts

### Transaction Processing

* Fund customer accounts
* Transfer funds between accounts
* Validate that sender and receiver accounts and their owners are active
* Prevent transfers with insufficient funds
* Prevent transfers to the same account
* Record debit and credit sides of transfers, linked by a transfer reference
* Lock the accounts involved while their balances change
* Maintain transaction status, type, and mode
* Retrieve customer transaction history
* Filter transactions by different criteria
* Paginated transaction retrieval

## Technology Stack

* Python
* SQLAlchemy
* SQLAlchemy AsyncIO
* MySQL
* PyMySQL
* aiomysql
* Alembic
* pydantic
* bcrypt
* python-dotenv
* asyncio
* pytest and pytest-asyncio (tests on SQLite with aiosqlite)

## Architecture

The repository is organized into separate layers:

```
Financial_Application
│
├── Application
│   ├── AccountApplication.py
│   ├── AccountTypesApplication.py
│   ├── CustomerApplication.py
│   ├── StaffApplication.py
│   └── TransactionApplication.py
│
├── ApplicationProcessing
│   ├── ProcessAccount.py
│   └── ProcessTransaction.py
│
├── Services
│   ├── Interfaces          (IUserService, IStaffService, ICustomerService, ...)
│   ├── Implementations     (UserService, StaffService, CustomerService, ...)
│   ├── Exceptions          (domain errors)
│   ├── Extensions          (error translation, response mapping)
│   └── Handler             (account number generation)
│
├── Data
│   ├── Interfaces          (IRepository, IUnitOfWork)
│   ├── Implementations     (Repository, UnitOfWork)
│   ├── Seed                (lookup seeding)
│   ├── Migrations          (Alembic)
│   ├── database_orm.py
│   └── database_orm_async.py
│
├── Models
│   ├── Entities            (SQLAlchemy entities)
│   ├── Dtos                (request and response models)
│   ├── Constants
│   └── Pagination
│
├── Infrastructure
│   ├── DependencyInjection (composition root)
│   ├── Logging
│   └── Security.py         (password hashing)
│
├── Api                     (reserved for API routers)
├── tests
├── docs
└── main.py
```

The structure separates application orchestration from business services and persistence logic. See [docs/architecture.md](docs/architecture.md) for details.

## Database

The application uses MySQL with SQLAlchemy.

Both synchronous and asynchronous database configurations are included in the repository: the asynchronous one (SQLAlchemy's `AsyncSession` with the `aiomysql` driver) is used by the application, the synchronous one by Alembic.

Configuration is loaded from environment variables.

Expected variables include:

```
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=your_database_name
BCRYPT_ROUNDS=12    # optional: cost of password hashing (4 to 31, default 12)
```

## Asynchronous Database Access

The application uses Python's asynchronous programming model for database operations.

The asynchronous database layer creates an SQLAlchemy async engine and manages sessions using `AsyncSession`.

This allows database operations to be performed without blocking the application's execution flow.

## Transaction Processing

Transactions are handled by the service layer through the unit of work and the generic repository.

### Account Funding

When an account is funded, the application:

1. Checks that the request is a deposit (credit).
2. Retrieves the customer's account and locks it.
3. Validates that the account and its owner are active.
4. Updates the account balance.
5. Creates a credit transaction.
6. Records the transaction as completed.

### Fund Transfer

A transfer involves two accounts.

The application:

1. Retrieves and locks the sender and receiver accounts in one query, in a fixed order.
2. Verifies that both accounts and their owners are active.
3. Ensures the sender and receiver are different.
4. Checks that sufficient funds are available.
5. Debits the sender.
6. Credits the receiver.
7. Creates corresponding debit and credit transaction records that share a transfer reference.

The balance updates and transaction creation are saved in one database transaction: all of them or none.

## Transaction History

The application can retrieve transaction history associated with users and accounts.

Transactions can also be filtered using information such as:

* Account
* Account type
* Transaction type
* Transaction mode
* Transaction status
* Sender
* A search term (account owner's name or email, account number)

Filtering and pagination are done by the database. The non-paginated list returns the 15 most recent matching transactions.

## Data Models

The domain model includes entities representing:

* Users
* Customers
* Staff
* Roles
* Accounts
* Account types
* Transactions
* Transaction types
* Transaction modes
* Transaction statuses

These models are mapped to the relational database through SQLAlchemy.

## Repository Pattern and Unit of Work

Database operations are separated from the business logic through a generic repository and a unit of work.

Each service operation receives a unit of work from its caller, reads and stages changes through the unit of work's repositories, and saves them in one transaction. Services implement interfaces and are wired together in a composition root (`Infrastructure/DependencyInjection`). When an operation cannot be carried out, the service raises a domain error (for example not found, conflict or business rule) and nothing is saved.

This provides a clearer separation between:

```
Application
    ↓
Application Processing
    ↓
Services (interfaces)
    ↓
Unit of Work / Repositories
    ↓
SQLAlchemy
    ↓
MySQL
```

## Database Migrations

Alembic is included for managing changes to the database schema.

The repository contains:

```
Data/Migrations/
alembic.ini
```

which can be used to maintain database migrations as the models evolve. Create or update the database schema with:

```bash
alembic upgrade head
```

The lookup data (roles, account types, transaction types, modes and statuses) is seeded by the application: missing rows are added when it starts, all of them on the first run. It can also be run on its own:

```bash
python -m Data.Seed.lookup_seed
```

## Running the Application

Clone the repository:

```bash
git clone https://github.com/Slimcent/Financial_Application.git
cd Financial_Application
```

Create a `.env` file containing the required MySQL configuration:

```
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=your_database_name
```

Install the required Python packages and make sure a MySQL database is available:

```bash
pip install -r requirements.txt
alembic upgrade head
```

Run the application with:

```
python main.py
```

The current entry point executes the asynchronous application workflow using `asyncio`.

The unit tests need no MySQL database (they run on an in-memory SQLite database):

```bash
pytest
```

## Project Highlights

This project demonstrates several backend software engineering concepts:

* Python asynchronous programming
* Layered application architecture
* Object-oriented programming
* Repository pattern and unit of work
* Service layer pattern with service interfaces
* Dependency injection through a composition root
* Domain errors
* SQLAlchemy ORM
* Asynchronous SQLAlchemy sessions
* Relational database modeling
* MySQL integration
* Environment-based configuration
* Database transactions
* Account balance management
* Financial transaction processing
* Data transfer objects (pydantic request and response models)
* Pagination and filtering
* Database migrations with Alembic
* Unit tests on an isolated in-memory database

## Project Status

This project is a banking application prototype focused primarily on backend architecture, persistence, account management and financial transaction workflows.

It serves as a practical implementation of Python backend development concepts and relational database design.

## Author

**Obinna Vincent Achara**

GitHub: [@Slimcent](https://github.com/Slimcent)
