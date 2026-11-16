"""GUID helpers for raw SQL (aiomysql) queries.

SQLAlchemy's Uuid type stores GUID keys on MySQL as CHAR(32): the 32 lowercase hex digits without dashes.
Raw SQL must send and read exactly that format, otherwise it will not match rows written by the ORM
(PyMySQL would send a uuid.UUID as the 36-character dashed string).
"""
import uuid
from typing import Any, Optional

from Models.Entities.column_types import uuid7


def new_guid() -> uuid.UUID:
    """A new GUID for a primary key inserted through raw SQL: time-ordered (UUIDv7), like the ORM's keys."""
    return uuid7()


def to_db_guid(value: uuid.UUID | str) -> str:
    """Convert a GUID (or its string form) to the CHAR(32) value stored in the database."""
    if not isinstance(value, uuid.UUID):
        value = uuid.UUID(str(value))
    return value.hex


def from_db_guid(value: Any) -> Optional[uuid.UUID]:
    """Convert a CHAR(32) value read through raw SQL back to a GUID (None stays None)."""
    if value is None or isinstance(value, uuid.UUID):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("ascii")
    return uuid.UUID(value)
