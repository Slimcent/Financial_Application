"""Fixtures for the migration tests (helpers in migration_sql.py)."""
import io

import pytest
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from tests.unit.Data.Migrations.migration_sql import MIGRATIONS_DIR, apply_to_schema, normalise


@pytest.fixture(scope="module")
def script():
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return ScriptDirectory.from_config(config)


@pytest.fixture(scope="module")
def revision_sql(script):
    """The SQL a revision's upgrade() / downgrade() emits for MySQL, as a list of statements."""

    def _revision_sql(revision, direction):
        module = script.get_revision(revision).module
        buffer = io.StringIO()
        context = MigrationContext.configure(dialect_name="mysql", opts={"as_sql": True, "output_buffer": buffer})
        with Operations.context(context):
            getattr(module, direction)()
        return [statement for statement in map(normalise, buffer.getvalue().split(";\n")) if statement]

    return _revision_sql


@pytest.fixture(scope="module")
def upgrade_path(script):
    """The revision ids from the base to the head, in the order `alembic upgrade head` applies them."""
    return [revision.revision for revision in reversed(list(script.walk_revisions()))]


@pytest.fixture(scope="module")
def head_schema(revision_sql, upgrade_path):
    """The schema a new database has after `alembic upgrade head`: every revision's upgrade(), in order."""
    schema = {}
    for revision in upgrade_path:
        schema = apply_to_schema(revision_sql(revision, "upgrade"), schema)
    return schema


@pytest.fixture(scope="module")
def entity_schema(metadata_ddl):
    return apply_to_schema(metadata_ddl("mysql://"))
