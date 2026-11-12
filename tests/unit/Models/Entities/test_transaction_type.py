"""TransactionTypes (lookup): mapping of Models/Entities/transaction_type.py."""
from Models.Entities import TransactionType


def test_table_name():
    assert TransactionType.__tablename__ == "TransactionTypes"


def test_columns(column_definitions):
    assert column_definitions(TransactionType) == {"Id": ("INTEGER", False), "Name": ("VARCHAR(50)", False)}


def test_has_no_relationships(relationship_definitions):
    # referenced one-way from Transaction.transaction_type
    assert relationship_definitions(TransactionType) == {}


def test_constraints(foreign_keys_of, unique_constraints_of, indexes_of, check_constraints_of):
    constraints = (foreign_keys_of(TransactionType), unique_constraints_of(TransactionType), indexes_of(TransactionType),
                   check_constraints_of(TransactionType))

    assert constraints == ({}, {("Name",)}, set(), {})
