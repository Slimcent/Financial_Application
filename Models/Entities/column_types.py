"""Column types, key generation and UTC defaults shared by all entities."""
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Uuid
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import Dialect
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.types import TypeDecorator

# ---------------------------------------------------------------------------
# GUID keys
# ---------------------------------------------------------------------------

# GUID keys are stored as CHAR(32): the 32 lowercase hex digits, without dashes.
# native_uuid=False keeps CHAR(32) on every backend; without it SQLAlchemy switches to a native UUID
# column where one exists (e.g. MariaDB 10.7+), which would no longer match the CHAR(32) foreign keys.
GUID = Uuid(as_uuid=True, native_uuid=False)

_UUID7_LOCK = threading.Lock()
_uuid7_last_timestamp = 0


def uuid7() -> uuid.UUID:
    """A time-ordered UUID, version 7 (RFC 9562).

    Layout: 48-bit Unix time in milliseconds, version (7), 12 bits of sub-millisecond time
    (RFC 9562 method 3), variant, 62 random bits. Values sort by creation time, both as UUIDs and in
    their CHAR(32) form, so new keys are appended to the end of the primary-key index instead of
    being scattered through it. Within one process the values strictly increase, even when the
    system clock is coarse or steps back.
    """
    global _uuid7_last_timestamp
    now_ns = time.time_ns()
    timestamp = (now_ns // 1_000_000) << 12 | (now_ns % 1_000_000) * 4096 // 1_000_000
    with _UUID7_LOCK:
        if timestamp <= _uuid7_last_timestamp:
            timestamp = _uuid7_last_timestamp + 1
        _uuid7_last_timestamp = timestamp
    unix_ms, sub_ms = timestamp >> 12, timestamp & 0xFFF
    random_bits = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
    return uuid.UUID(int=(unix_ms & ((1 << 48) - 1)) << 80 | 0x7 << 76 | sub_ms << 64 | 0b10 << 62 | random_bits)


# ---------------------------------------------------------------------------
# UTC timestamps
# ---------------------------------------------------------------------------

def utc_now() -> datetime:
    """The current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class UtcDateTime(TypeDecorator):
    """A timestamp that is always UTC.

    Stored without a time zone, as UTC: DATETIME(6) (microsecond precision) on MySQL/MariaDB,
    DATETIME elsewhere. Aware datetimes are converted to UTC before they are written; naive datetimes
    are taken to be UTC already. Values read back are timezone-aware (UTC).
    """

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name in ("mysql", "mariadb"):
            return dialect.type_descriptor(mysql.DATETIME(fsp=6))
        return dialect.type_descriptor(DateTime())

    def process_bind_param(self, value: Optional[datetime], dialect: Dialect) -> Optional[datetime]:
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value: Optional[datetime], dialect: Dialect) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class UtcTimestampDefault(ColumnElement):
    """Database-side default: the current UTC time, written in each database's own SQL.

    Used for rows inserted outside the ORM (raw SQL), so they get UTC timestamps too, independent of
    the connection's time zone. Every form is already parenthesised, so it renders identically in
    every SQLAlchemy version (MySQL expression defaults need 8.0.13+, MariaDB 10.2+).
    """

    type = DateTime()
    inherit_cache = True


@compiles(UtcTimestampDefault)
def _utc_timestamp_default(element: UtcTimestampDefault, compiler: Any, **kw: Any) -> str:
    return "CURRENT_TIMESTAMP"


@compiles(UtcTimestampDefault, "mysql")
@compiles(UtcTimestampDefault, "mariadb")
def _utc_timestamp_default_mysql(element: UtcTimestampDefault, compiler: Any, **kw: Any) -> str:
    return "(UTC_TIMESTAMP(6))"


@compiles(UtcTimestampDefault, "sqlite")
def _utc_timestamp_default_sqlite(element: UtcTimestampDefault, compiler: Any, **kw: Any) -> str:
    # SQLite's 'now' is UTC; padded to microseconds to match how SQLAlchemy stores DATETIME values.
    return "(STRFTIME('%Y-%m-%d %H:%M:%f000', 'now'))"


@compiles(UtcTimestampDefault, "postgresql")
def _utc_timestamp_default_postgresql(element: UtcTimestampDefault, compiler: Any, **kw: Any) -> str:
    return "(timezone('utc', now()))"


UTC_NOW_SERVER_DEFAULT = UtcTimestampDefault()
