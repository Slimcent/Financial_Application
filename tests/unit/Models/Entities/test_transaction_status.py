"""TransactionStatuses (lookup): mapping of Models/Entities/transaction_status.py."""
from Models.Entities import TransactionStatus


def test_table_name():
    assert TransactionStatus.__tablename__ == "TransactionStatuses"


def test_columns(column_definitions):
    assert column_definitions(TransactionStatus) == {"Id": ("INTEGER", False), "Name": ("VARCHAR(50)", False)}


def test_has_no_relationships(relationship_definitions):
    # referenced one-way from Transaction.transaction_status
    assert relationship_definitions(TransactionStatus) == {}


def test_constraints(foreign_keys_of, unique_constraints_of, indexes_of, check_constraints_of):
    constraints = (foreign_keys_of(TransactionStatus), unique_constraints_of(TransactionStatus), indexes_of(TransactionStatus),
                   check_constraints_of(TransactionStatus))

    assert constraints == ({}, {("Name",)}, set(), {})
