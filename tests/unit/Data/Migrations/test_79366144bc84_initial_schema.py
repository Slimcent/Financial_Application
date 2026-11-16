"""The initial migration (Data/Migrations/versions/79366144bc84_initial_schema.py) against the entity metadata.

The migrations are rendered offline as MySQL SQL (Alembic "as_sql" mode into a buffer) and compared with the
DDL that Base.metadata produces for MySQL. No database is contacted and env.py is not used.

The initial migration creates every table. Later revisions change the schema step by step, so the schema a new
database has after `alembic upgrade head` (the initial migration and every later revision) must be exactly the
schema the entities define.
"""
import ast

import pytest

from Models.Entities import Base
from tests.unit.Data.Migrations.migration_sql import (CREATE_TABLE, DROP_TABLE, MIGRATIONS_DIR, REFERENCES,
                                                      TABLE_NAMES, apply_to_schema)

REVISION = "79366144bc84"


@pytest.fixture(scope="module")
def offline_sql(revision_sql):
    """The SQL the initial migration's upgrade() / downgrade() emits for MySQL, as a list of statements."""

    def _offline_sql(direction):
        return revision_sql(REVISION, direction)

    return _offline_sql


@pytest.fixture(scope="module")
def migration_schema(offline_sql):
    """The schema the initial migration alone creates."""
    return apply_to_schema(offline_sql("upgrade"))


# ---------------------------------------------------------------------------
# Revision history
# ---------------------------------------------------------------------------

def test_initial_migration_is_the_only_base(script):
    assert script.get_bases() == [REVISION]
    assert script.get_revision(REVISION).down_revision is None


def test_revision_history_is_linear_from_the_initial_migration_to_a_single_head(script, upgrade_path):
    assert len(script.get_heads()) == 1
    assert upgrade_path[0] == REVISION
    assert upgrade_path[-1] == script.get_heads()[0]
    for previous, revision in zip(upgrade_path, upgrade_path[1:]):
        assert script.get_revision(revision).down_revision == previous


def test_env_targets_the_entity_metadata():
    tree = ast.parse((MIGRATIONS_DIR / "env.py").read_text(encoding="utf-8"))
    imports = {(node.module, alias.name) for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
               for alias in node.names}
    targets = [ast.unparse(node.value) for node in ast.walk(tree) if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == "target_metadata" for target in node.targets)]

    assert ("Models.Entities", "Base") in imports
    assert targets == ["Base.metadata"]


# ---------------------------------------------------------------------------
# upgrade(): the initial migration creates every table; with the later revisions, exactly the entity schema
# ---------------------------------------------------------------------------

def test_upgrade_creates_every_entity_table(migration_schema):
    assert sorted(migration_schema) == sorted(TABLE_NAMES)


@pytest.mark.parametrize("table_name", TABLE_NAMES)
def test_table_definition_matches_the_entity(head_schema, entity_schema, table_name):
    # columns (types, nullability, defaults), primary key, foreign keys (ON DELETE), unique and check constraints
    assert head_schema[table_name]["definition"] == entity_schema[table_name]["definition"]


@pytest.mark.parametrize("table_name", TABLE_NAMES)
def test_indexes_match_the_entity(head_schema, entity_schema, table_name):
    assert head_schema[table_name]["indexes"] == entity_schema[table_name]["indexes"]


@pytest.mark.parametrize("table_name", TABLE_NAMES)
def test_updated_at_trigger_matches_the_entity(head_schema, entity_schema, table_name):
    assert head_schema[table_name]["triggers"] == entity_schema[table_name]["triggers"]
    assert len(head_schema[table_name]["triggers"]) == 1


@pytest.mark.parametrize("table_name", TABLE_NAMES)
def test_initial_migration_creates_every_index_and_trigger(migration_schema, entity_schema, table_name):
    # Later revisions have not added or removed indexes or triggers: the initial migration creates all of them.
    assert migration_schema[table_name]["indexes"] == entity_schema[table_name]["indexes"]
    assert migration_schema[table_name]["triggers"] == entity_schema[table_name]["triggers"]


def test_upgrade_creates_referenced_tables_first(offline_sql):
    created = []
    for statement in offline_sql("upgrade"):
        if match := CREATE_TABLE.match(statement):
            assert set(REFERENCES.findall(statement)) - {match.group(1)} <= set(created)
            created.append(match.group(1))


# ---------------------------------------------------------------------------
# downgrade()
# ---------------------------------------------------------------------------

def test_downgrade_only_drops_tables(offline_sql):
    statements = offline_sql("downgrade")

    assert all(DROP_TABLE.match(statement) for statement in statements)
    assert sorted(DROP_TABLE.match(statement).group(1) for statement in statements) == sorted(TABLE_NAMES)


def test_downgrade_drops_referencing_tables_first(offline_sql):
    dropped = [DROP_TABLE.match(statement).group(1) for statement in offline_sql("downgrade")]
    for table in Base.metadata.sorted_tables:
        for foreign_key in table.foreign_key_constraints:
            assert dropped.index(table.name) < dropped.index(foreign_key.referred_table.name)
