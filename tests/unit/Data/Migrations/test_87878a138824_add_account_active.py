"""The revision that adds Accounts.Active (Data/Migrations/versions/87878a138824_add_account_active.py).

Rendered offline as MySQL SQL; no database is contacted. See migration_sql.py.
"""
from tests.unit.Data.Migrations.migration_sql import apply_to_schema, column_clause

REVISION = "87878a138824"
INITIAL_REVISION = "79366144bc84"


def test_revision_follows_the_initial_migration(script):
    assert script.get_revision(REVISION).down_revision == INITIAL_REVISION


def test_revision_is_the_head(script):
    assert script.get_heads() == [REVISION]


def test_upgrade_adds_the_active_column_as_the_entity_defines_it(revision_sql, entity_schema):
    expected = f"ALTER TABLE `Accounts` ADD COLUMN {column_clause(entity_schema, 'Accounts', 'Active')}"

    assert revision_sql(REVISION, "upgrade") == [expected]


def test_existing_accounts_stay_active(revision_sql):
    # The column is added to a table that may already hold accounts: it needs a default, and that default is true.
    clause = column_clause(apply_to_schema(revision_sql(REVISION, "upgrade"),
                                           {"Accounts": {"definition": set(), "indexes": set(), "triggers": set()}}),
                           "Accounts", "Active")

    assert clause == "`Active` BOOL NOT NULL DEFAULT true"


def test_downgrade_drops_only_the_active_column(revision_sql):
    assert revision_sql(REVISION, "downgrade") == ["ALTER TABLE `Accounts` DROP COLUMN `Active`"]


def test_downgrade_restores_the_schema_of_the_previous_revision(revision_sql):
    before = apply_to_schema(revision_sql(INITIAL_REVISION, "upgrade"))
    upgraded = apply_to_schema(revision_sql(REVISION, "upgrade"), before)

    assert apply_to_schema(revision_sql(REVISION, "downgrade"), upgraded) == before
    assert upgraded != before
