"""AccountTypes (lookup): mapping of Models/Entities/account_type.py."""
from Models.Entities import AccountType

COLUMNS = {"Id": ("INTEGER", False), "Type": ("VARCHAR(50)", False)}
RELATIONSHIPS = {
    "accounts": ("Account", "ONETOMANY", True, "account_type", frozenset({"AccountTypes.Id=Accounts.AccountTypeId"})),
}


def test_table_name():
    assert AccountType.__tablename__ == "AccountTypes"


def test_columns(column_definitions):
    assert column_definitions(AccountType) == COLUMNS


def test_relationships(relationship_definitions):
    assert relationship_definitions(AccountType) == RELATIONSHIPS


def test_constraints(foreign_keys_of, unique_constraints_of, indexes_of, check_constraints_of):
    assert (foreign_keys_of(AccountType), unique_constraints_of(AccountType), indexes_of(AccountType),
            check_constraints_of(AccountType)) == ({}, {("Type",)}, set(), {})
