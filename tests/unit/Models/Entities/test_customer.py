"""Customers: mapping of Models/Entities/customer.py."""
from Models.Entities import Customer

COLUMNS = {"Id": ("CHAR(32)", False), "UserId": ("CHAR(32)", False), "Address": ("VARCHAR(255)", True)}
RELATIONSHIPS = {"user": ("User", "MANYTOONE", False, "customer", frozenset({"Customers.UserId=Users.Id"}))}


def test_table_name():
    assert Customer.__tablename__ == "Customers"


def test_columns(column_definitions):
    assert column_definitions(Customer) == COLUMNS


def test_relationships(relationship_definitions):
    assert relationship_definitions(Customer) == RELATIONSHIPS


def test_foreign_keys(foreign_keys_of):
    assert foreign_keys_of(Customer) == {("UserId",): ("Users", ("Id",))}


def test_one_customer_record_per_user(unique_constraints_of, indexes_of, check_constraints_of):
    assert (unique_constraints_of(Customer), indexes_of(Customer), check_constraints_of(Customer)) == \
           ({("UserId",)}, set(), {})
