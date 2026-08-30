# Financial Application

Financial Application is a Python-based banking application that demonstrates the implementation of common banking operations using a layered backend architecture, asynchronous database access, SQLAlchemy and MySQL.

The project separates application workflows, business logic, persistence, models, DTOs, infrastructure and utility components to keep responsibilities organized and maintainable.

## Features

### Customer and User Management

* Customer management
* Staff management
* User management
* Account ownership and customer relationships
* Authentication service
* Active account and user validation

### Account Management

* Create and manage customer accounts
* Support different account types
* Retrieve accounts by user
* Retrieve account details by account number
* Track individual account balances
* Calculate total balances across customer accounts

### Transaction Processing

* Fund customer accounts
* Transfer funds between accounts
* Validate sender and receiver accounts
* Prevent transfers with insufficient funds
* Prevent transfers to the same account
* Record debit and credit sides of transfers
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
* python-dotenv
* asyncio

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
├── Dtos
│   └── Request and response models
│
├── Infrastructure
│   └── Application constants and infrastructure configuration
│
├── Repository
│   └── Database access and persistence operations
│
├── Service
│   ├── AccountService.py
│   ├── AccountTypeService.py
│   ├── AuthenticationService.py
│   ├── CustomerService.py
│   ├── StaffService.py
│   ├── UserService.py
│   └── transaction_service.py
│
├── SqlQueries
│   └── SQL-related functionality
│
├── Utility
│   └── Shared application utilities
│
├── models
│   ├── User
│   ├── Customer
│   ├── Staff
│   ├── Account
│   ├── Account Type
│   ├── Transaction
│   ├── Transaction Type
│   ├── Transaction Mode
│   ├── Transaction Status
│   └── Role
│
├── alembic
│   └── Database migration files
│
├── database_orm.py
├── database_orm_async.py
└── main.py
```

The structure separates application orchestration from business services and persistence logic.

## Database

The application uses MySQL with SQLAlchemy.

Both synchronous and asynchronous database configurations are included in the repository, while the asynchronous implementation uses SQLAlchemy's `AsyncSession` and the `aiomysql` MySQL driver.

Database configuration is loaded from environment variables.

Expected variables include:

```
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=your_database_name
```

## Asynchronous Database Access

The application uses Python's asynchronous programming model for database operations.

The asynchronous database layer creates an SQLAlchemy async engine and manages sessions using `AsyncSession`.

This allows database operations to be performed without blocking the application's execution flow.

## Transaction Processing

Transactions are handled through the service and repository layers.

### Account Funding

When an account is funded, the application:

1. Retrieves the account.
2. Validates the account and associated user.
3. Updates the account balance.
4. Creates a credit transaction.
5. Records the transaction as completed.

### Fund Transfer

A transfer involves two accounts.

The application:

1. Retrieves the sender account.
2. Verifies that the sender is active.
3. Checks that sufficient funds are available.
4. Retrieves the receiver account.
5. Ensures the sender and receiver are different.
6. Debits the sender.
7. Credits the receiver.
8. Creates corresponding debit and credit transaction records.

The balance updates and transaction creation are performed within the same database transaction.

## Transaction History

The application can retrieve transaction history associated with users and accounts.

Transactions can also be filtered using information such as:

* Account
* Account type
* Transaction type
* Transaction mode
* Transaction status

Pagination support is available for retrieving larger collections of transactions.

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

## Repository Pattern

Database operations are separated from the business logic through repository classes.

The service layer communicates with repositories instead of embedding persistence operations directly into application workflows.

This provides a clearer separation between:

```
Application
    ↓
Application Processing
    ↓
Services
    ↓
Repositories
    ↓
SQLAlchemy
    ↓
MySQL
```

## Database Migrations

Alembic is included for managing changes to the database schema.

The repository contains:

```
alembic/
alembic.ini
```

which can be used to maintain database migrations as the models evolve.

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

Make sure the required Python packages and a MySQL database are available.

Run the application with:

```
python main.py
```

The current entry point executes the asynchronous application workflow using `asyncio`.

## Project Highlights

This project demonstrates several backend software engineering concepts:

* Python asynchronous programming
* Layered application architecture
* Object-oriented programming
* Repository pattern
* Service layer pattern
* SQLAlchemy ORM
* Asynchronous SQLAlchemy sessions
* Relational database modeling
* MySQL integration
* Environment-based configuration
* Database transactions
* Account balance management
* Financial transaction processing
* Data transfer objects
* Pagination and filtering
* Database migrations with Alembic

## Project Status

This project is a banking application prototype focused primarily on backend architecture, persistence, account management and financial transaction workflows.

It serves as a practical implementation of Python backend development concepts and relational database design.

## Author

**Obinna Vincent Achara**

GitHub: [@Slimcent](https://github.com/Slimcent)
