"""Roles (lookup): mapping of Models/Entities/Roles.py."""
from Models.Entities import Role

COLUMNS = {"Id": ("INTEGER", False), "Name": ("VARCHAR(100)", False)}
RELATIONSHIPS = {"Users": ("User", "ONETOMANY", True, "Role", frozenset({"Roles.Id=Users.RoleId"}))}


def test_table_name():
    assert Role.__tablename__ == "Roles"


def test_columns(column_definitions):
    assert column_definitions(Role) == COLUMNS


def test_relationships(relationship_definitions):
    assert relationship_definitions(Role) == RELATIONSHIPS


def test_constraints(foreign_keys_of, unique_constraints_of, indexes_of, check_constraints_of):
    assert (foreign_keys_of(Role), unique_constraints_of(Role), indexes_of(Role), check_constraints_of(Role)) == \
           ({}, {("Name",)}, set(), {})
