"""Users: mapping of Models/Entities/user.py."""
from Models.Entities import User

COLUMNS = {
    "Id": ("CHAR(32)", False),
    "LastName": ("VARCHAR(100)", False),
    "FirstName": ("VARCHAR(100)", False),
    "Email": ("VARCHAR(255)", False),
    "RoleId": ("INTEGER", False),
    "Password": ("VARCHAR(255)", False),
    "Active": ("BOOL", False),
}
RELATIONSHIPS = {
    "Role": ("Role", "MANYTOONE", False, "Users", frozenset({"Users.RoleId=Roles.Id"})),
    "Staff": ("Staff", "ONETOMANY", False, "User", frozenset({"Users.Id=Staff.UserId"})),
    "customer": ("Customer", "ONETOMANY", False, "user", frozenset({"Users.Id=Customers.UserId"})),
    "accounts": ("Account", "ONETOMANY", True, "user", frozenset({"Users.Id=Accounts.UserId"})),
    "transactions": ("Transaction", "ONETOMANY", True, "user", frozenset({"Users.Id=Transactions.UserId"})),
    "sent_transactions": ("Transaction", "ONETOMANY", True, "sender", frozenset({"Users.Id=Transactions.SenderId"})),
}
FOREIGN_KEYS = {("RoleId",): ("Roles", ("Id",))}
UNIQUE_CONSTRAINTS = {("Email",)}
INDEXES = {("RoleId",)}


def test_table_name():
    assert User.__tablename__ == "Users"


def test_columns(column_definitions):
    assert column_definitions(User) == COLUMNS


def test_relationships(relationship_definitions):
    assert relationship_definitions(User) == RELATIONSHIPS


def test_foreign_keys(foreign_keys_of):
    assert foreign_keys_of(User) == FOREIGN_KEYS


def test_unique_constraints_and_indexes(unique_constraints_of, indexes_of):
    assert (unique_constraints_of(User), indexes_of(User)) == (UNIQUE_CONSTRAINTS, INDEXES)


def test_no_check_constraints(check_constraints_of):
    assert check_constraints_of(User) == {}


def test_new_user_is_active_by_default():
    active = User.__table__.c["Active"]

    assert active.default.arg is True
    assert active.server_default is not None
