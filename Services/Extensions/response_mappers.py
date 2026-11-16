"""Mapping of entities to the response models, shared by the services.

The mappers read only what they are given. Relationships are never loaded implicitly (they are ``raise_on_sql``),
so a service passes the related objects it loaded (through includes) or just created explicitly. Money stays a
Decimal, as it is stored.
"""
from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Optional

from Models.Dtos.Response.AccountResponse import AccountResponse
from Models.Dtos.Response.AccountTypeResponse import AccountTypeResponse
from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Response.UserResponse import UserResponse
from Models.Dtos.Response.transaction_response import TransactionResponse, TransactionsResponse
from Models.Entities import Account, AccountType, Customer, Role, Staff, Transaction, User

ZERO = Decimal("0.00")

# Includes that load what the transaction mappers read.
TRANSACTION_INCLUDES = ("account.account_type", "transaction_type", "transaction_mode", "transaction_status", "sender")
TRANSACTIONS_INCLUDES = (*TRANSACTION_INCLUDES, "user.customer", "user.Staff")


def to_account_type_response(account_type: AccountType) -> AccountTypeResponse:
    return AccountTypeResponse(account_type_id=account_type.Id, name=account_type.Type)


def to_accounts_response(account: Account, account_type: Optional[AccountType] = None) -> AccountsResponse:
    """One account. ``account_type`` defaults to the loaded ``account.account_type``."""
    account_type = account_type if account_type is not None else account.account_type
    return AccountsResponse(
        account_id=account.Id,
        account_number=account.AccountNumber,
        balance=account.Balance,
        account_type_id=account.AccountTypeId,
        account_type=account_type.Type if account_type is not None else None,
        active=account.Active,
    )


def to_accounts_responses(accounts: Iterable[Account]) -> list[AccountsResponse]:
    """Accounts with their loaded account types, ordered by account type."""
    return [to_accounts_response(account) for account in sorted(accounts, key=lambda item: item.AccountTypeId)]


def total_balance(accounts: Iterable[Account]) -> Decimal:
    return sum((account.Balance for account in accounts), ZERO)


def to_user_response(user: User, role: Optional[Role], *, customer: Optional[Customer] = None,
                     staff: Optional[Staff] = None, accounts: Sequence[AccountsResponse] = ()) -> UserResponse:
    """A user, with its customer or staff record and its accounts when given."""
    return UserResponse(
        user_id=user.Id,
        customer_id=customer.Id if customer is not None else None,
        staff_id=staff.Id if staff is not None else None,
        last_name=user.LastName,
        first_name=user.FirstName,
        email=user.Email,
        address=customer.Address if customer is not None else None,
        position=staff.Position if staff is not None else None,
        role_id=role.Id if role is not None else user.RoleId,
        role_name=role.Name if role is not None else None,
        accounts=list(accounts),
        active=user.Active,
        created_at=user.CreatedAt,
    )


def to_staff_response(staff: Staff) -> UserResponse:
    """A staff member loaded with the includes ``"User.Role"``."""
    return to_user_response(staff.User, staff.User.Role, staff=staff)


def to_customer_response(customer: Customer) -> UserResponse:
    """A customer loaded with the includes ``"user.Role"`` and ``"user.accounts.account_type"``."""
    user = customer.user
    return to_user_response(user, user.Role, customer=customer, accounts=to_accounts_responses(user.accounts))


def to_account_response(user: User, accounts: Sequence[Account], *, customer: Optional[Customer] = None,
                        balance: Optional[Decimal] = None) -> AccountResponse:
    """A user's accounts (each with its loaded account type and its own active flag) and their total balance;
    ``active`` is the user's; ``balance`` is the balance of the one account a response is about, when there is one."""
    return AccountResponse(
        user_id=user.Id,
        customer_id=customer.Id if customer is not None else None,
        last_name=user.LastName,
        first_name=user.FirstName,
        address=customer.Address if customer is not None else None,
        email=user.Email,
        active=user.Active,
        accounts=to_accounts_responses(accounts),
        balance=balance,
        total_balance=total_balance(accounts),
    )


def to_transaction_response(transaction: Transaction) -> TransactionResponse:
    """A transaction loaded with TRANSACTION_INCLUDES."""
    account = transaction.account
    sender = transaction.sender
    return TransactionResponse(
        account_id=account.Id,
        account_number=account.AccountNumber,
        amount=transaction.Amount,
        account_type_id=account.AccountTypeId,
        account_type=account.account_type.Type,
        transaction_type_id=transaction.TransactionTypeId,
        transaction_type=transaction.transaction_type.Name,
        transaction_mode_id=transaction.TransactionModeId,
        transaction_mode=transaction.transaction_mode.Name,
        transaction_status_id=transaction.TransactionStatusId,
        transaction_status=transaction.transaction_status.Name,
        transaction_date=transaction.TransactionDate,
        description=transaction.Description,
        sender_id=transaction.SenderId,
        sender=_full_name(sender),
    )


def to_transactions_response(transaction: Transaction) -> TransactionsResponse:
    """A transaction with its account owner, loaded with TRANSACTIONS_INCLUDES."""
    user = transaction.user
    account = transaction.account
    customer = user.customer
    staff = user.Staff
    return TransactionsResponse(
        user_id=user.Id,
        last_name=user.LastName,
        first_name=user.FirstName,
        address=customer.Address if customer is not None else None,
        email=user.Email,
        account_id=account.Id,
        account_number=account.AccountNumber,
        amount=transaction.Amount,
        account_type_id=account.AccountTypeId,
        account_type=account.account_type.Type,
        transaction_type_id=transaction.TransactionTypeId,
        transaction_type=transaction.transaction_type.Name,
        transaction_mode_id=transaction.TransactionModeId,
        transaction_mode=transaction.transaction_mode.Name,
        transaction_status_id=transaction.TransactionStatusId,
        transaction_status=transaction.transaction_status.Name,
        transaction_date=transaction.TransactionDate,
        description=transaction.Description,
        customer_id=customer.Id if customer is not None else None,
        staff_id=staff.Id if staff is not None else None,
        sender_id=transaction.SenderId,
        sender=_full_name(transaction.sender),
    )


def _full_name(user: Optional[User]) -> Optional[str]:
    return f"{user.FirstName} {user.LastName}" if user is not None else None
