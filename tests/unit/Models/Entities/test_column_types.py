"""Column types, key generation and UTC defaults from Models/Entities/column_types.py."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.dialects.mysql import mariadb

from Models.Entities import column_types
from Models.Entities.column_types import GUID, UTC_NOW_SERVER_DEFAULT, UtcDateTime, utc_now, uuid7

WEST_AFRICA = timezone(timedelta(hours=1))
FIXED_TIME_NS = 1_767_225_600_123_456_789          # 2026-01-01 00:00:00.123456789 UTC


def _mariadb_with_native_uuid():
    dialect = mariadb.MariaDBDialect()
    dialect.server_version_info = (10, 11)          # a MariaDB version with a native UUID type
    return dialect


DIALECTS = {
    "mysql": mysql.dialect(),
    "mariadb": _mariadb_with_native_uuid(),
    "sqlite": sqlite.dialect(),
    "postgresql": postgresql.dialect(),
}


@pytest.fixture(params=list(DIALECTS), ids=list(DIALECTS))
def dialect_name(request):
    return request.param


@pytest.fixture
def frozen_clock(monkeypatch):
    """Freeze time.time_ns() for uuid7() and start from a clean 'last timestamp' (both restored afterwards)."""
    monkeypatch.setattr(column_types, "_uuid7_last_timestamp", 0)

    def _freeze(ns):
        monkeypatch.setattr(column_types.time, "time_ns", lambda: ns)

    _freeze(FIXED_TIME_NS)
    return _freeze


# ---------------------------------------------------------------------------
# uuid7
# ---------------------------------------------------------------------------

def test_uuid7_is_version_7_with_the_rfc_variant():
    value = uuid7()

    assert (value.version, value.variant) == (7, uuid.RFC_4122)


def test_uuid7_embeds_the_unix_time_in_milliseconds(frozen_clock):
    assert uuid7().int >> 80 == FIXED_TIME_NS // 1_000_000


@pytest.mark.parametrize("clock", ["frozen", "stepping-back"])
def test_uuid7_values_strictly_increase_even_when_the_clock_does_not(frozen_clock, clock):
    values = []
    for step in range(1_000):
        if clock == "stepping-back":
            frozen_clock(FIXED_TIME_NS - step * 1_000)
        values.append(uuid7())

    assert all(earlier < later for earlier, later in zip(values, values[1:]))


def test_uuid7_values_sort_by_creation_in_their_char32_form():
    values = [uuid7() for _ in range(10_000)]

    assert [value.hex for value in values] == sorted(value.hex for value in values)
    assert len(set(values)) == len(values)


# ---------------------------------------------------------------------------
# GUID
# ---------------------------------------------------------------------------

def test_guid_is_char32_on_every_database(dialect_name):
    assert str(GUID.compile(dialect=DIALECTS[dialect_name])) == "CHAR(32)"


def test_guid_is_written_as_32_lowercase_hex_digits():
    value = uuid.UUID("018f2b8c-9e6d-7a4e-9b7c-2a5d8e0f1c34")

    assert GUID.bind_processor(DIALECTS["mysql"])(value) == "018f2b8c9e6d7a4e9b7c2a5d8e0f1c34"


def test_guid_is_read_back_as_a_uuid():
    value = uuid7()

    assert GUID.result_processor(DIALECTS["mysql"], None)(value.hex) == value


# ---------------------------------------------------------------------------
# UTC timestamps
# ---------------------------------------------------------------------------

def test_utc_now_is_timezone_aware_utc():
    assert utc_now().tzinfo is timezone.utc


@pytest.mark.parametrize("dialect_name, expected", [
    ("mysql", "DATETIME(6)"),
    ("mariadb", "DATETIME(6)"),
    ("sqlite", "DATETIME"),
    ("postgresql", "TIMESTAMP WITHOUT TIME ZONE"),
])
def test_utc_datetime_column_type(dialect_name, expected):
    assert str(UtcDateTime().compile(dialect=DIALECTS[dialect_name])) == expected


@pytest.mark.parametrize("value, stored", [
    (datetime(2026, 1, 1, 10, 0, tzinfo=WEST_AFRICA), datetime(2026, 1, 1, 9, 0)),
    (datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc), datetime(2026, 1, 1, 9, 0)),
    (datetime(2026, 1, 1, 9, 0), datetime(2026, 1, 1, 9, 0)),
    (None, None),
], ids=["aware-other-zone", "aware-utc", "naive-taken-as-utc", "none"])
def test_utc_datetime_stores_naive_utc(value, stored):
    assert UtcDateTime().process_bind_param(value, DIALECTS["mysql"]) == stored


@pytest.mark.parametrize("value, loaded", [
    (datetime(2026, 1, 1, 9, 0, 0, 123456), datetime(2026, 1, 1, 9, 0, 0, 123456, tzinfo=timezone.utc)),
    (datetime(2026, 1, 1, 10, 0, tzinfo=WEST_AFRICA), datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)),
    (None, None),
], ids=["naive-from-database", "aware-from-driver", "none"])
def test_utc_datetime_loads_aware_utc(value, loaded):
    result = UtcDateTime().process_result_value(value, DIALECTS["mysql"])

    assert result == loaded
    assert result is None or result.tzinfo is timezone.utc


def test_utc_datetime_round_trip_keeps_the_instant_and_microseconds():
    utc_type, dialect, value = UtcDateTime(), DIALECTS["mysql"], utc_now()

    assert utc_type.process_result_value(utc_type.process_bind_param(value, dialect), dialect) == value


@pytest.mark.parametrize("dialect_name, expected", [
    ("mysql", "(UTC_TIMESTAMP(6))"),
    ("mariadb", "(UTC_TIMESTAMP(6))"),
    ("sqlite", "(STRFTIME('%Y-%m-%d %H:%M:%f000', 'now'))"),
    ("postgresql", "(timezone('utc', now()))"),
])
def test_utc_server_default_is_written_for_each_database(dialect_name, expected):
    assert str(UTC_NOW_SERVER_DEFAULT.compile(dialect=DIALECTS[dialect_name])) == expected
