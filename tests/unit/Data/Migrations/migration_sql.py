"""Helpers for the migration tests: the offline (MySQL) SQL of a revision and the schema a list of statements builds.

The migrations are rendered offline as MySQL SQL (Alembic "as_sql" mode into a buffer) and compared with the DDL
that Base.metadata produces for MySQL. No database is contacted and env.py is not used.
"""
import re
from pathlib import Path

from Models.Entities import Base

PROJECT_ROOT = Path(__file__).resolve().parents[4]
MIGRATIONS_DIR = PROJECT_ROOT / "Data" / "Migrations"
TABLE_NAMES = [table.name for table in Base.metadata.sorted_tables]

CREATE_TABLE = re.compile(r"CREATE TABLE `(\w+)` \((.*)\)$")
CREATE_INDEX = re.compile(r"CREATE (?:UNIQUE )?INDEX `\w+` ON `(\w+)`")
CREATE_TRIGGER = re.compile(r"CREATE TRIGGER `\w+` BEFORE UPDATE ON `(\w+)`")
ADD_COLUMN = re.compile(r"ALTER TABLE `(\w+)` ADD COLUMN ((`\w+`) .*)$")
DROP_COLUMN = re.compile(r"ALTER TABLE `(\w+)` DROP COLUMN (`\w+`)$")
DROP_TABLE = re.compile(r"DROP TABLE `(\w+)`$")
REFERENCES = re.compile(r"REFERENCES `(\w+)`")


def normalise(statement):
    return " ".join(statement.split()).rstrip(";").strip()


def apply_to_schema(statements, schema=None):
    """Apply DDL statements to a schema description and return it:
    {table: {"definition": {column / constraint clauses}, "indexes": {...}, "triggers": {...}}}.

    Understands the statements the migrations emit: CREATE TABLE / INDEX / TRIGGER and ALTER TABLE ... ADD / DROP
    COLUMN. Any other statement fails the test, so a migration cannot do something these tests do not check.
    """
    schema = {} if schema is None else {table: {part: set(items) for part, items in parts.items()}
                                        for table, parts in schema.items()}
    for statement in map(normalise, statements):
        if match := CREATE_TABLE.match(statement):
            clauses = [clause.strip() for clause in re.split(r", (?=`|CONSTRAINT )", match.group(2))]
            schema.setdefault(match.group(1), {"definition": set(), "indexes": set(), "triggers": set()})
            schema[match.group(1)]["definition"] = set(clauses)
        elif match := CREATE_INDEX.match(statement):
            schema[match.group(1)]["indexes"].add(statement)
        elif match := CREATE_TRIGGER.match(statement):
            schema[match.group(1)]["triggers"].add(statement)
        elif match := ADD_COLUMN.match(statement):
            schema[match.group(1)]["definition"].add(match.group(2))
        elif match := DROP_COLUMN.match(statement):
            definition = schema[match.group(1)]["definition"]
            dropped = {clause for clause in definition if clause.startswith(f"{match.group(2)} ")}
            assert dropped, f"{statement}: no such column"
            definition -= dropped
        elif statement:
            raise AssertionError(f"unexpected statement: {statement}")
    return schema


def column_clause(schema, table_name, column_name):
    """The definition clause of one column, e.g. "`Active` BOOL NOT NULL DEFAULT true"."""
    clauses = [clause for clause in schema[table_name]["definition"] if clause.startswith(f"`{column_name}` ")]
    assert len(clauses) == 1, schema[table_name]["definition"]
    return clauses[0]
