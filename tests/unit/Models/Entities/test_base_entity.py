"""The shared declarative Base and BaseEntity (Models/Entities/base_entity.py), verified through every entity."""
import importlib
import inspect as pyinspect
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint, inspect
from sqlalchemy.exc import InvalidRequestError

import Models.Entities
from Models.Entities import Base, BaseEntity
from Models.Entities.base_entity import LAZY, NAMING_CONVENTION, updated_at_trigger_sql
from Models.Entities.column_types import GUID, UtcDateTime, UtcTimestampDefault

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ENTITY_PACKAGE_DIR = Path(pyinspect.getfile(BaseEntity)).parent
MYSQL_IDENTIFIER_MAX_LENGTH = 64

TABLES = Base.metadata.sorted_tables
FOREIGN_KEYS = [fk for table in TABLES for fk in sorted(table.foreign_key_constraints, key=lambda fk: fk.name)]
RELATIONSHIPS = [rel for mapper in sorted(Base.registry.mappers, key=lambda m: m.class_.__name__)
                 for rel in sorted(mapper.relationships, key=lambda rel: rel.key)]

AUDIT_COLUMN_DEFINITIONS = {
    "CreatedAt": ("DATETIME(6)", False),
    "UpdatedAt": ("DATETIME(6)", False),
    "CreatedBy": ("CHAR(32)", True),
    "UpdatedBy": ("CHAR(32)", True),
}

# (object in loaded_graph, many-to-one relationship, object it must resolve to)
MANY_TO_ONE_IN_SESSION = [
    ("user", "Role", "role"),
    ("staff", "User", "user"),
    ("customer", "user", "user"),
    ("account", "user", "user"),
    ("account", "account_type", "account_type"),
    ("transaction", "account", "account"),
    ("transaction", "user", "user"),
    ("transaction", "transaction_type", "transaction_type"),
    ("transaction", "transaction_mode", "transaction_mode"),
    ("transaction", "transaction_status", "transaction_status"),
]

# relationships that can only be loaded with SQL (collections and the reverse side of one-to-ones)
NEEDS_SQL = [
    ("role", "Users"),
    ("account_type", "accounts"),
    ("user", "Staff"),
    ("user", "customer"),
    ("user", "accounts"),
    ("user", "transactions"),
    ("user", "sent_transactions"),
    ("account", "transactions"),
]


def _discover_entities():
    entities = set()
    for path in ENTITY_PACKAGE_DIR.glob("*.py"):
        module = importlib.import_module(f"Models.Entities.{path.stem}")
        for _, member in pyinspect.getmembers(module, pyinspect.isclass):
            if issubclass(member, BaseEntity) and member.__module__ == module.__name__ and member is not BaseEntity:
                entities.add(member)
    return entities


def _expected_name(table, item):
    columns = "_".join(column.name for column in item.columns)
    if isinstance(item, PrimaryKeyConstraint):
        return f"pk_{table.name}"
    if isinstance(item, ForeignKeyConstraint):
        return f"fk_{table.name}_{columns}_{item.referred_table.name}"
    if isinstance(item, UniqueConstraint):
        return f"uq_{table.name}_{columns}"
    return f"ix_{table.name}_{columns}"


# ---------------------------------------------------------------------------
# Shared declarative base and registration
# ---------------------------------------------------------------------------

def test_every_entity_is_registered_exported_and_covered_here(all_entities):
    discovered = _discover_entities()
    exported = {getattr(Models.Entities, name) for name in Models.Entities.__all__}

    assert discovered == set(all_entities)
    assert discovered <= exported
    assert set(Base.metadata.tables) == {entity.__tablename__ for entity in discovered}


def test_entity_uses_the_shared_base_and_metadata(entity):
    assert issubclass(entity, BaseEntity)
    assert entity.__table__.metadata is Base.metadata


def test_metadata_uses_the_naming_convention():
    assert {key: Base.metadata.naming_convention[key] for key in NAMING_CONVENTION} == NAMING_CONVENTION


def test_annotations_map_to_the_shared_column_types():
    assert Base.type_annotation_map[uuid.UUID] is GUID
    assert isinstance(Base.type_annotation_map[datetime], UtcDateTime)


def test_base_entity_is_abstract_without_a_table_or_primary_key():
    assert BaseEntity.__abstract__ is True
    assert "__table__" not in vars(BaseEntity)
    assert not any(column.primary_key for column in (getattr(BaseEntity, name).column for name in AUDIT_COLUMN_DEFINITIONS))


def test_mappers_configure_without_sqlalchemy_warnings():
    # A fresh interpreter, so the mappers are configured here for the first time.
    code = ("import warnings; from sqlalchemy.exc import SAWarning; warnings.simplefilter('error', SAWarning); "
            "import Models.Entities; from sqlalchemy.orm import configure_mappers; configure_mappers()")
    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# Primary keys
# ---------------------------------------------------------------------------

def test_main_entity_has_a_time_ordered_guid_primary_key(guid_key_entity, mysql_type):
    (key,) = guid_key_entity.__table__.primary_key.columns
    generated = key.default.arg(None)

    assert (key.name, mysql_type(key), key.nullable) == ("Id", "CHAR(32)", False)
    assert isinstance(generated, uuid.UUID) and generated.version == 7


def test_lookup_entity_has_an_auto_increment_integer_primary_key(integer_key_entity, mysql_type):
    (key,) = integer_key_entity.__table__.primary_key.columns

    assert (key.name, mysql_type(key), key.nullable, key.default) == ("Id", "INTEGER", False, None)
    assert key is integer_key_entity.__table__.autoincrement_column


# ---------------------------------------------------------------------------
# Audit columns and UTC timestamps
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("column, expected", AUDIT_COLUMN_DEFINITIONS.items(), ids=list(AUDIT_COLUMN_DEFINITIONS))
def test_audit_column_type_and_nullability(entity, column, expected, mysql_type):
    table_column = entity.__table__.c[column]

    assert (mysql_type(table_column), table_column.nullable) == expected


@pytest.mark.parametrize("column", ["CreatedAt", "UpdatedAt"])
def test_timestamp_defaults_to_utc_in_the_application_and_the_database(entity, column):
    table_column = entity.__table__.c[column]

    assert table_column.default.arg(None).tzinfo is timezone.utc
    assert isinstance(table_column.server_default.arg, UtcTimestampDefault)


def test_updated_at_is_refreshed_in_utc_on_orm_updates(entity):
    assert entity.__table__.c["UpdatedAt"].onupdate.arg(None).tzinfo is timezone.utc


@pytest.mark.parametrize("column", ["CreatedBy", "UpdatedBy"])
def test_audit_user_column_is_optional_and_not_filled_automatically(entity, column):
    table_column = entity.__table__.c[column]

    assert (table_column.default, table_column.server_default, table_column.onupdate) == (None, None, None)
    assert not table_column.foreign_keys


def test_new_row_gets_one_utc_creation_instant(entity, fire_before_insert):
    row = fire_before_insert(entity())

    assert row.CreatedAt.tzinfo is timezone.utc
    assert row.UpdatedAt == row.CreatedAt


def test_explicit_creation_time_is_kept(entity, fire_before_insert):
    created_at = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    row = fire_before_insert(entity(CreatedAt=created_at))

    assert (row.CreatedAt, row.UpdatedAt) == (created_at, created_at)


@pytest.mark.parametrize("url", ["mysql://", "mariadb://"])
def test_every_table_gets_an_updated_at_trigger_on_mysql(metadata_ddl, url):
    triggers = {statement for statement in metadata_ddl(url) if statement.startswith("CREATE TRIGGER")}

    assert triggers == {updated_at_trigger_sql(table.name) for table in TABLES}


def test_updated_at_trigger_only_fills_in_updates_that_did_not_set_it():
    sql = updated_at_trigger_sql("Users")

    assert "BEFORE UPDATE ON `Users` FOR EACH ROW" in sql
    assert sql.endswith("SET NEW.`UpdatedAt` = IF(NEW.`UpdatedAt` <=> OLD.`UpdatedAt`, UTC_TIMESTAMP(6), NEW.`UpdatedAt`)")


@pytest.mark.parametrize("url", ["sqlite://", "postgresql://"])
def test_schema_compiles_for_other_databases_without_mysql_specific_sql(metadata_ddl, url):
    statements = metadata_ddl(url)

    assert sum(statement.startswith("CREATE TABLE") for statement in statements) == len(TABLES)
    assert not [statement for statement in statements if "TRIGGER" in statement or "UTC_TIMESTAMP" in statement
                or "`" in statement]


# ---------------------------------------------------------------------------
# Naming convention
# ---------------------------------------------------------------------------

def test_constraint_and_index_names_follow_the_convention(entity):
    table = entity.__table__
    for item in [*table.constraints, *table.indexes]:
        if isinstance(item, CheckConstraint):
            assert item.name.startswith(f"ck_{table.name}_")
        else:
            assert item.name == _expected_name(table, item)
        assert len(item.name) <= MYSQL_IDENTIFIER_MAX_LENGTH


# ---------------------------------------------------------------------------
# Foreign keys (every foreign key of every table)
# ---------------------------------------------------------------------------

@pytest.fixture(params=FOREIGN_KEYS, ids=[fk.name for fk in FOREIGN_KEYS])
def foreign_key(request):
    return request.param


def test_foreign_key_references_a_primary_or_unique_key(foreign_key):
    referenced = tuple(element.column.name for element in foreign_key.elements)
    keys = {tuple(column.name for column in constraint.columns) for constraint in foreign_key.referred_table.constraints
            if isinstance(constraint, (PrimaryKeyConstraint, UniqueConstraint))}

    assert referenced in keys


def test_foreign_key_columns_have_the_referenced_types(foreign_key, mysql_type):
    assert [mysql_type(element.parent) for element in foreign_key.elements] == \
           [mysql_type(element.column) for element in foreign_key.elements]


def test_foreign_key_restricts_deletes(foreign_key):
    assert foreign_key.ondelete == "RESTRICT"


def test_foreign_key_columns_lead_an_index(foreign_key):
    columns = tuple(foreign_key.column_keys)
    table = foreign_key.table
    leading = [tuple(column.name for column in item.columns)[:len(columns)]
               for item in [*table.indexes, *table.constraints]
               if isinstance(item, (PrimaryKeyConstraint, UniqueConstraint)) or item in table.indexes]

    assert columns in leading


# ---------------------------------------------------------------------------
# Relationships (every relationship of every entity)
# ---------------------------------------------------------------------------

@pytest.fixture(params=RELATIONSHIPS, ids=[f"{rel.parent.class_.__name__}.{rel.key}" for rel in RELATIONSHIPS])
def relationship(request):
    return request.param


def test_relationship_never_loads_implicitly(relationship):
    assert relationship.lazy == LAZY == "raise_on_sql"


def test_back_populates_is_mutual(relationship):
    if relationship.back_populates is None:
        assert relationship.mapper.class_.__tablename__ in {"TransactionTypes", "TransactionModes", "TransactionStatuses"}
    else:
        assert relationship.mapper.relationships[relationship.back_populates].back_populates == relationship.key


def test_parent_side_leaves_delete_checks_to_the_database(relationship):
    expected = "all" if relationship.direction.name == "ONETOMANY" else False

    assert relationship.passive_deletes == expected


# ---------------------------------------------------------------------------
# Loading without SQL (what an async session can do)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("owner, attribute, target", MANY_TO_ONE_IN_SESSION,
                         ids=[f"{owner}.{attribute}" for owner, attribute, _ in MANY_TO_ONE_IN_SESSION])
def test_many_to_one_already_in_the_session_is_returned_without_sql(loaded_graph, owner, attribute, target):
    assert getattr(loaded_graph[owner], attribute) is loaded_graph[target]


@pytest.mark.parametrize("owner, attribute", NEEDS_SQL, ids=[f"{owner}.{attribute}" for owner, attribute in NEEDS_SQL])
def test_relationship_that_needs_sql_raises_instead_of_loading(loaded_graph, owner, attribute):
    with pytest.raises(InvalidRequestError, match="raise_on_sql"):
        getattr(loaded_graph[owner], attribute)


@pytest.mark.parametrize("attribute", ["account", "user", "sender", "transaction_type"])
def test_many_to_one_not_in_the_session_raises_instead_of_loading(orphan_transaction, attribute):
    with pytest.raises(InvalidRequestError, match="raise_on_sql"):
        getattr(orphan_transaction, attribute)


def test_many_to_one_with_a_null_foreign_key_is_none_without_sql(loaded_graph):
    assert loaded_graph["transaction"].sender is None
