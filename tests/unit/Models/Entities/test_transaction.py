"""Transactions: mapping of Models/Entities/transaction.py."""
from datetime import datetime, timezone

from Models.Entities import Transaction
from Models.Entities.column_types import UtcTimestampDefault

COLUMNS = {
    "Id": ("CHAR(32)", False),
    "AccountId": ("CHAR(32)", False),
    "TransactionTypeId": ("INTEGER", False),
    "TransactionModeId": ("INTEGER", False),
    "TransactionStatusId": ("INTEGER", False),
    "Amount": ("DECIMAL(10, 2)", False),
    "TransactionDate": ("DATETIME(6)", False),
    "Description": ("VARCHAR(255)", True),
    "UserId": ("CHAR(32)", False),
    "SenderId": ("CHAR(32)", True),
    "TransferReference": ("CHAR(32)", True),
}
RELATIONSHIPS = {
    "account": ("Account", "MANYTOONE", False, "transactions", frozenset({"Transactions.AccountId=Accounts.Id"})),
    "transaction_type": ("TransactionType", "MANYTOONE", False, None,
                         frozenset({"Transactions.TransactionTypeId=TransactionTypes.Id"})),
    "transaction_mode": ("TransactionMode", "MANYTOONE", False, None,
                         frozenset({"Transactions.TransactionModeId=TransactionModes.Id"})),
    "transaction_status": ("TransactionStatus", "MANYTOONE", False, None,
                           frozenset({"Transactions.TransactionStatusId=TransactionStatuses.Id"})),
    "user": ("User", "MANYTOONE", False, "transactions", frozenset({"Transactions.UserId=Users.Id"})),
    "sender": ("User", "MANYTOONE", False, "sent_transactions", frozenset({"Transactions.SenderId=Users.Id"})),
}
FOREIGN_KEYS = {
    ("AccountId", "UserId"): ("Accounts", ("Id", "UserId")),     # the account must belong to the transaction's user
    ("TransactionTypeId",): ("TransactionTypes", ("Id",)),
    ("TransactionModeId",): ("TransactionModes", ("Id",)),
    ("TransactionStatusId",): ("TransactionStatuses", ("Id",)),
    ("UserId",): ("Users", ("Id",)),
    ("SenderId",): ("Users", ("Id",)),                           # the sender stays a user
}
INDEXES = {
    ("AccountId", "UserId"),
    ("TransactionTypeId",),
    ("TransactionModeId",),
    ("TransactionStatusId",),
    ("TransactionDate",),
    ("UserId",),
    ("SenderId",),
}


def test_table_name():
    assert Transaction.__tablename__ == "Transactions"


def test_columns(column_definitions):
    assert column_definitions(Transaction) == COLUMNS


def test_relationships(relationship_definitions):
    assert relationship_definitions(Transaction) == RELATIONSHIPS


def test_foreign_keys(foreign_keys_of):
    assert foreign_keys_of(Transaction) == FOREIGN_KEYS


def test_indexes(indexes_of):
    assert indexes_of(Transaction) == INDEXES


def test_a_transfer_has_at_most_one_debit_and_one_credit_row(unique_constraints_of):
    assert unique_constraints_of(Transaction) == {("TransferReference", "TransactionModeId")}


def test_amount_must_be_positive(check_constraints_of):
    assert check_constraints_of(Transaction) == {"ck_Transactions_amount_positive": "Amount > 0"}


def test_account_and_user_relationships_write_different_columns():
    account, user = Transaction.account.property, Transaction.user.property

    assert {column.name for column in account.local_columns} == {"AccountId"}
    assert {column.name for column in user.local_columns} == {"UserId"}


def test_transaction_date_is_a_utc_timestamp_with_a_database_default():
    transaction_date = Transaction.__table__.c["TransactionDate"]

    assert transaction_date.default.arg(None).tzinfo is timezone.utc
    assert isinstance(transaction_date.server_default.arg, UtcTimestampDefault)


def test_transaction_date_defaults_to_the_creation_instant(fire_before_insert):
    transaction = fire_before_insert(Transaction())

    assert transaction.TransactionDate == transaction.CreatedAt == transaction.UpdatedAt
    assert transaction.TransactionDate.tzinfo is timezone.utc


def test_explicit_transaction_date_is_kept(fire_before_insert):
    value_date = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    transaction = fire_before_insert(Transaction(TransactionDate=value_date))

    assert transaction.TransactionDate == value_date
    assert transaction.CreatedAt != value_date
