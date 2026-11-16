"""TransactionModes (lookup): mapping of Models/Entities/transaction_mode.py."""
from Models.Entities import TransactionMode


def test_table_name():
    assert TransactionMode.__tablename__ == "TransactionModes"


def test_columns(column_definitions):
    assert column_definitions(TransactionMode) == {"Id": ("INTEGER", False), "Name": ("VARCHAR(50)", False)}


def test_has_no_relationships(relationship_definitions):
    # referenced one-way from Transaction.transaction_mode
    assert relationship_definitions(TransactionMode) == {}


def test_constraints(foreign_keys_of, unique_constraints_of, indexes_of, check_constraints_of):
    constraints = (foreign_keys_of(TransactionMode), unique_constraints_of(TransactionMode), indexes_of(TransactionMode),
                   check_constraints_of(TransactionMode))

    assert constraints == ({}, {("Name",)}, set(), {})
