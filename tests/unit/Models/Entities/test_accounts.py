"""Accounts: mapping of Models/Entities/accounts.py."""
from decimal import Decimal

from Models.Entities import Account

COLUMNS = {
    "Id": ("CHAR(32)", False),
    "UserId": ("CHAR(32)", False),
    "AccountTypeId": ("INTEGER", False),
    "AccountNumber": ("VARCHAR(10)", False),
    "Balance": ("DECIMAL(18, 2)", False),
}
RELATIONSHIPS = {
    "user": ("User", "MANYTOONE", False, "accounts", frozenset({"Accounts.UserId=Users.Id"})),
    "account_type": ("AccountType", "MANYTOONE", False, "accounts",
                     frozenset({"Accounts.AccountTypeId=AccountTypes.Id"})),
    # joined on AccountId only, although Transactions references Accounts (Id, UserId)
    "transactions": ("Transaction", "ONETOMANY", True, "account", frozenset({"Accounts.Id=Transactions.AccountId"})),
}
FOREIGN_KEYS = {("UserId",): ("Users", ("Id",)), ("AccountTypeId",): ("AccountTypes", ("Id",))}
UNIQUE_CONSTRAINTS = {
    ("AccountNumber",),
    ("UserId", "AccountTypeId"),   # one account per account type for each user
    ("Id", "UserId"),              # target of the Transactions (AccountId, UserId) foreign key
}


def test_table_name():
    assert Account.__tablename__ == "Accounts"


def test_columns(column_definitions):
    assert column_definitions(Account) == COLUMNS


def test_relationships(relationship_definitions):
    assert relationship_definitions(Account) == RELATIONSHIPS


def test_foreign_keys(foreign_keys_of):
    assert foreign_keys_of(Account) == FOREIGN_KEYS


def test_unique_constraints_and_indexes(unique_constraints_of, indexes_of):
    assert (unique_constraints_of(Account), indexes_of(Account)) == (UNIQUE_CONSTRAINTS, {("AccountTypeId",)})


def test_balance_cannot_be_negative(check_constraints_of):
    assert check_constraints_of(Account) == {"ck_Accounts_balance_non_negative": "Balance >= 0"}


def test_balance_is_a_decimal_starting_at_zero():
    balance = Account.__table__.c["Balance"]

    assert balance.type.asdecimal is True
    assert balance.default.arg == Decimal("0.00")
    assert balance.server_default.arg == "0.00"
