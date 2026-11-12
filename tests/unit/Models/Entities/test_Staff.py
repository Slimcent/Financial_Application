"""Staff: mapping of Models/Entities/Staff.py."""
from Models.Entities import Staff

COLUMNS = {"Id": ("CHAR(32)", False), "UserId": ("CHAR(32)", False), "Position": ("VARCHAR(100)", False)}
RELATIONSHIPS = {"User": ("User", "MANYTOONE", False, "Staff", frozenset({"Staff.UserId=Users.Id"}))}


def test_table_name():
    assert Staff.__tablename__ == "Staff"


def test_columns(column_definitions):
    assert column_definitions(Staff) == COLUMNS


def test_relationships(relationship_definitions):
    assert relationship_definitions(Staff) == RELATIONSHIPS


def test_foreign_keys(foreign_keys_of):
    assert foreign_keys_of(Staff) == {("UserId",): ("Users", ("Id",))}


def test_one_staff_record_per_user(unique_constraints_of, indexes_of, check_constraints_of):
    assert (unique_constraints_of(Staff), indexes_of(Staff), check_constraints_of(Staff)) == ({("UserId",)}, set(), {})
