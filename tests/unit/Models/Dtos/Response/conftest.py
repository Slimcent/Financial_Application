"""Shared fixtures for the response-model tests (Models/Dtos/Response).

Valid payloads hold the Python values the services pass (UUIDs, Decimals, aware datetimes); the tests also build
responses from the string forms a JSON client sends back. `entity_graph` builds transient entities (no session,
no database) to check that the services' response mappers produce valid responses.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from Models.Entities import Account, AccountType, Customer, Role, Staff, Transaction, TransactionMode
from Models.Entities import TransactionStatus, TransactionType, User

USER_ID = uuid.UUID("3f2b8c9e-6d4a-4e1f-9b7c-2a5d8e0f1c34")
CUSTOMER_ID = uuid.UUID("5a1c9e7b-2d4f-4b8a-9c6e-0d3f1a2b4c6e")
STAFF_ID = uuid.UUID("9d8c7b6a-5f4e-4d3c-8b2a-1f0e9d8c7b6a")
ACCOUNT_ID = uuid.UUID("b7e4d1a2-9c3f-4a6b-8e5d-1f0c2b3a4d5e")
SENDER_ID = uuid.UUID("0c1d2e3f-4a5b-4c6d-9e7f-8a9b0c1d2e3f")
CREATED_AT = datetime(2026, 11, 15, 9, 30, tzinfo=timezone.utc)
TRANSACTION_DATE = datetime(2026, 11, 15, 10, 45, 12, 123456, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Valid payloads (a fresh dict per test)
# ---------------------------------------------------------------------------

@pytest.fixture
def accounts_response_payload():
    return {"account_id": ACCOUNT_ID, "account_number": "2600000001", "balance": Decimal("100.00"),
            "account_type_id": 1, "account_type": "Savings", "active": True}


@pytest.fixture
def account_type_response_payload():
    return {"account_type_id": 1, "name": "Savings"}


@pytest.fixture
def role_response_payload():
    return {"role_id": 1, "name": "Customer"}


@pytest.fixture
def login_response_payload():
    return {"user_id": USER_ID, "last_name": "Lovelace", "first_name": "Ada", "email": "example1@example.com",
            "role_id": 1, "role_name": "Customer", "account_type_id": 1, "account_type": "Savings",
            "balance": Decimal("100.00"), "position": None}


@pytest.fixture
def user_response_payload(accounts_response_payload):
    return {"user_id": USER_ID, "customer_id": CUSTOMER_ID, "staff_id": None, "last_name": "Lovelace",
            "first_name": "Ada", "email": "example1@example.com", "address": "1 Main Street", "position": None,
            "role_id": 1, "role_name": "Customer", "accounts": [accounts_response_payload], "active": True,
            "created_at": CREATED_AT}


@pytest.fixture
def transaction_response_payload():
    return {"account_id": ACCOUNT_ID, "account_number": "2600000001", "amount": Decimal("25.50"),
            "account_type_id": 1, "account_type": "Savings", "transaction_type_id": 2, "transaction_type": "Transfer",
            "transaction_mode_id": 1, "transaction_mode": "Credit", "transaction_status_id": 2,
            "transaction_status": "Completed", "transaction_date": TRANSACTION_DATE, "description": "Rent",
            "sender_id": SENDER_ID, "sender": "Ben Okafor"}


@pytest.fixture
def transactions_response_payload(transaction_response_payload):
    return {**transaction_response_payload, "user_id": USER_ID, "last_name": "Lovelace", "first_name": "Ada",
            "address": "1 Main Street", "email": "example1@example.com", "customer_id": CUSTOMER_ID, "staff_id": None}


@pytest.fixture
def account_response_payload(accounts_response_payload, transaction_response_payload):
    return {"user_id": USER_ID, "customer_id": CUSTOMER_ID, "last_name": "Lovelace", "first_name": "Ada",
            "address": "1 Main Street", "email": "example1@example.com", "active": True,
            "accounts": [accounts_response_payload],
            "transactions": [transaction_response_payload], "balance": Decimal("100.00"),
            "total_balance": Decimal("150.00")}


@pytest.fixture
def paged_response_payload(account_type_response_payload):
    return {"total_count": 3, "page": 2, "page_size": 2, "items": [account_type_response_payload]}


# ---------------------------------------------------------------------------
# Invalid values
# ---------------------------------------------------------------------------

# Invalid values of a field that is optional: None is valid there (it means "no value").
_INVALID_MONEY = [
    pytest.param("abc", id="text"),
    pytest.param("", id="empty"),
    pytest.param("NaN", id="not-a-number"),
    pytest.param("Infinity", id="infinity"),
    pytest.param(float("nan"), id="float-not-a-number"),
    pytest.param(float("inf"), id="float-infinity"),
    pytest.param(True, id="boolean"),
    pytest.param([1], id="list"),
]
# GUID identifiers are UUIDs: in Python even a valid text form is refused (JSON clients send text, see the tests).
_INVALID_GUIDS = [
    pytest.param("not-a-uuid", id="text"),
    pytest.param("3f2b8c9e-6d4a-4e1f-9b7c", id="truncated"),
    pytest.param("3f2b8c9e-6d4a-4e1f-9b7c-2a5d8e0f1c34", id="valid-text-form"),
    pytest.param(12345, id="integer"),
    pytest.param(USER_ID.bytes, id="bytes"),
]
# Integer identifiers are ints: not a bool, not a float (even a whole one), not text (even digits).
_INVALID_INTEGERS = [
    pytest.param("abc", id="text"),
    pytest.param("2", id="digits-text"),
    pytest.param(1.5, id="fraction"),
    pytest.param(2.0, id="whole-float"),
    pytest.param("1.5", id="fraction-text"),
    pytest.param(True, id="boolean"),
]
_NONE = pytest.param(None, id="none")


@pytest.fixture(params=[*_INVALID_MONEY, _NONE])
def invalid_money(request):
    """Invalid values of a required money field."""
    return request.param


@pytest.fixture(params=_INVALID_MONEY)
def invalid_optional_money(request):
    return request.param


@pytest.fixture(params=[*_INVALID_GUIDS, _NONE])
def invalid_guid(request):
    """Invalid values of a required GUID field."""
    return request.param


@pytest.fixture(params=_INVALID_GUIDS)
def invalid_optional_guid(request):
    return request.param


@pytest.fixture(params=[*_INVALID_INTEGERS, _NONE])
def invalid_integer(request):
    """Invalid values of a required integer field."""
    return request.param


@pytest.fixture(params=_INVALID_INTEGERS)
def invalid_optional_integer(request):
    return request.param


@pytest.fixture(params=[
    pytest.param(12345, id="integer"),
    pytest.param(Decimal("1"), id="decimal"),
    pytest.param(["text"], id="list"),
])
def invalid_text(request):
    return request.param


@pytest.fixture(params=[
    pytest.param("yesterday", id="text"),
    pytest.param("2026-13-01T00:00:00Z", id="invalid-month"),
    pytest.param([2026, 11, 15], id="list"),
])
def invalid_datetime(request):
    return request.param


@pytest.fixture(params=[
    pytest.param((Decimal("100.00"), Decimal("100.00")), id="decimal"),
    pytest.param(("100.50", Decimal("100.50")), id="text"),
    pytest.param((100, Decimal("100")), id="integer"),
    pytest.param(("0.00", Decimal("0.00")), id="zero"),
    pytest.param(("9999999999999999.99", Decimal("9999999999999999.99")), id="largest-balance"),
    pytest.param((0.1, Decimal("0.1")), id="float"),
    pytest.param((1234567.05, Decimal("1234567.05")), id="float-with-cents"),
    pytest.param((-25.5, Decimal("-25.5")), id="negative-float"),
])
def valid_money(request):
    """(value given, Decimal kept): the value is kept exactly, with its places. A float is taken by its shortest text
    form, so it gets no binary rounding digits (0.1 -> Decimal("0.1"))."""
    return request.param


# ---------------------------------------------------------------------------
# Entities the services map (transient: no session, no database)
# ---------------------------------------------------------------------------

@pytest.fixture
def entity_graph():
    """A customer (Ada, two accounts, one incoming transfer from Ben) and a staff member (Dee), with every
    relationship the response mappers read set on the objects."""
    customer_role = Role(Id=1, Name="Customer")
    staff_role = Role(Id=2, Name="Staff")
    savings = AccountType(Id=1, Type="Savings")
    current = AccountType(Id=2, Type="Current")

    ada = User(Id=USER_ID, LastName="Lovelace", FirstName="Ada", Email="example1@example.com", RoleId=1,
               Password="hash", Active=True, CreatedAt=CREATED_AT)
    ada.Role = customer_role
    customer = Customer(Id=CUSTOMER_ID, UserId=USER_ID, Address="1 Main Street")
    customer.user = ada

    ben = User(Id=SENDER_ID, LastName="Okafor", FirstName="Ben", Email="example2@example.com", RoleId=1,
               Password="hash", Active=True, CreatedAt=CREATED_AT)

    current_account = Account(Id=uuid.UUID(int=2), UserId=USER_ID, AccountTypeId=2, AccountNumber="2600000002",
                              Balance=Decimal("50.00"), Active=True)
    current_account.account_type = current
    current_account.user = ada
    savings_account = Account(Id=ACCOUNT_ID, UserId=USER_ID, AccountTypeId=1, AccountNumber="2600000001",
                              Balance=Decimal("100.00"), Active=True)
    savings_account.account_type = savings
    savings_account.user = ada

    transaction = Transaction(Id=uuid.UUID(int=9), AccountId=ACCOUNT_ID, UserId=USER_ID, TransactionTypeId=2,
                              TransactionModeId=1, TransactionStatusId=2, Amount=Decimal("25.50"),
                              TransactionDate=TRANSACTION_DATE, Description="Rent", SenderId=SENDER_ID)
    transaction.account = savings_account
    transaction.user = ada
    transaction.sender = ben
    transaction.transaction_type = TransactionType(Id=2, Name="Transfer")
    transaction.transaction_mode = TransactionMode(Id=1, Name="Credit")
    transaction.transaction_status = TransactionStatus(Id=2, Name="Completed")

    dee = User(Id=uuid.UUID(int=4), LastName="Mensah", FirstName="Dee", Email="example4@example.com", RoleId=2,
               Password="hash", Active=False, CreatedAt=CREATED_AT)
    dee.Role = staff_role
    staff = Staff(Id=STAFF_ID, UserId=dee.Id, Position="Teller")
    staff.User = dee

    return SimpleNamespace(customer_role=customer_role, staff_role=staff_role, savings=savings, current=current,
                           ada=ada, customer=customer, ben=ben, savings_account=savings_account,
                           current_account=current_account, transaction=transaction, dee=dee, staff=staff)
