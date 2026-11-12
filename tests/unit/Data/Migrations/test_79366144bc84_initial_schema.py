"""The initial migration (Data/Migrations/versions/79366144bc84_initial_schema.py) against the entity metadata.

The migration is rendered offline as MySQL SQL (Alembic "as_sql" mode into a buffer) and compared with the
DDL that Base.metadata produces for MySQL. No database is contacted and env.py is not used.
"""
import ast
import io
import re
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from Models.Entities import Base

REVISION = "79366144bc84"
PROJECT_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = PROJECT_ROOT / "Data" / "Migrations"
TABLE_NAMES = [table.name for table in Base.metadata.sorted_tables]

_CREATE_TABLE = re.compile(r"CREATE TABLE `(\w+)` \((.*)\)$")
_CREATE_INDEX = re.compile(r"CREATE (?:UNIQUE )?INDEX `\w+` ON `(\w+)`")
_CREATE_TRIGGER = re.compile(r"CREATE TRIGGER `\w+` BEFORE UPDATE ON `(\w+)`")
_DROP_TABLE = re.compile(r"DROP TABLE `(\w+)`$")
_REFERENCES = re.compile(r"REFERENCES `(\w+)`")


def _normalise(statement):
    return " ".join(statement.split()).rstrip(";").strip()


def _schema_by_table(statements):
    """{table: {"definition": {column / constraint clauses}, "indexes": {...}, "triggers": {...}}}."""
    schema = {}
    for statement in map(_normalise, statements):
        if match := _CREATE_TABLE.match(statement):
            clauses = [clause.strip() for clause in re.split(r", (?=`|CONSTRAINT )", match.group(2))]
            schema.setdefault(match.group(1), {"definition": set(), "indexes": set(), "triggers": set()})
            schema[match.group(1)]["definition"] = set(clauses)
        elif match := _CREATE_INDEX.match(statement):
            schema[match.group(1)]["indexes"].add(statement)
        elif match := _CREATE_TRIGGER.match(statement):
            schema[match.group(1)]["triggers"].add(statement)
        elif statement:
            raise AssertionError(f"unexpected statement: {statement}")
    return schema


@pytest.fixture(scope="module")
def script():
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return ScriptDirectory.from_config(config)


@pytest.fixture(scope="module")
def offline_sql(script):
    """The SQL the migration's upgrade() / downgrade() emits for MySQL, as a list of statements."""
    module = script.get_revision(REVISION).module

    def _offline_sql(direction):
        buffer = io.StringIO()
        context = MigrationContext.configure(dialect_name="mysql", opts={"as_sql": True, "output_buffer": buffer})
        with Operations.context(context):
            getattr(module, direction)()
        return [statement for statement in map(_normalise, buffer.getvalue().split(";\n")) if statement]

    return _offline_sql


@pytest.fixture(scope="module")
def migration_schema(offline_sql):
    return _schema_by_table(offline_sql("upgrade"))


@pytest.fixture(scope="module")
def entity_schema(metadata_ddl):
    return _schema_by_table(metadata_ddl("mysql://"))


# ---------------------------------------------------------------------------
# Revision history
# ---------------------------------------------------------------------------

def test_initial_migration_is_the_only_base_and_head(script):
    assert (script.get_bases(), script.get_heads()) == ([REVISION], [REVISION])
    assert script.get_revision(REVISION).down_revision is None


def test_env_targets_the_entity_metadata():
    tree = ast.parse((MIGRATIONS_DIR / "env.py").read_text(encoding="utf-8"))
    imports = {(node.module, alias.name) for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
               for alias in node.names}
    targets = [ast.unparse(node.value) for node in ast.walk(tree) if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == "target_metadata" for target in node.targets)]

    assert ("Models.Entities", "Base") in imports
    assert targets == ["Base.metadata"]


# ---------------------------------------------------------------------------
# upgrade(): the migration creates exactly the schema the entities define
# ---------------------------------------------------------------------------

def test_upgrade_creates_every_entity_table(migration_schema):
    assert sorted(migration_schema) == sorted(TABLE_NAMES)


@pytest.mark.parametrize("table_name", TABLE_NAMES)
def test_table_definition_matches_the_entity(migration_schema, entity_schema, table_name):
    # columns (types, nullability, defaults), primary key, foreign keys (ON DELETE), unique and check constraints
    assert migration_schema[table_name]["definition"] == entity_schema[table_name]["definition"]


@pytest.mark.parametrize("table_name", TABLE_NAMES)
def test_indexes_match_the_entity(migration_schema, entity_schema, table_name):
    assert migration_schema[table_name]["indexes"] == entity_schema[table_name]["indexes"]


@pytest.mark.parametrize("table_name", TABLE_NAMES)
def test_updated_at_trigger_matches_the_entity(migration_schema, entity_schema, table_name):
    assert migration_schema[table_name]["triggers"] == entity_schema[table_name]["triggers"]
    assert len(migration_schema[table_name]["triggers"]) == 1


def test_upgrade_creates_referenced_tables_first(offline_sql):
    created = []
    for statement in offline_sql("upgrade"):
        if match := _CREATE_TABLE.match(statement):
            assert set(_REFERENCES.findall(statement)) - {match.group(1)} <= set(created)
            created.append(match.group(1))


# ---------------------------------------------------------------------------
# downgrade()
# ---------------------------------------------------------------------------

def test_downgrade_only_drops_tables(offline_sql):
    statements = offline_sql("downgrade")

    assert all(_DROP_TABLE.match(statement) for statement in statements)
    assert sorted(_DROP_TABLE.match(statement).group(1) for statement in statements) == sorted(TABLE_NAMES)


def test_downgrade_drops_referencing_tables_first(offline_sql):
    dropped = [_DROP_TABLE.match(statement).group(1) for statement in offline_sql("downgrade")]
    for table in Base.metadata.sorted_tables:
        for foreign_key in table.foreign_key_constraints:
            assert dropped.index(table.name) < dropped.index(foreign_key.referred_table.name)
