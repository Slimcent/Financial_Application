import pytest

from Models.Dtos.Request.RoleRequest import RoleRequest


@pytest.mark.parametrize("raw, expected", [
    ("Customer", "Customer"),
    ("  Branch Manager ", "Branch Manager"),
    ("x" * 100, "x" * 100),
], ids=["simple", "trimmed", "max-length"])
def test_valid_name_is_accepted(raw, expected):
    assert RoleRequest(name=raw).name == expected


def test_missing_name_is_rejected(assert_rejected):
    assert_rejected(RoleRequest, {}, "name", "missing")


def test_blank_name_is_rejected(blank_value, assert_rejected):
    assert_rejected(RoleRequest, {"name": blank_value}, "name")


@pytest.mark.parametrize("value, error_type", [
    ("x" * 101, "string_too_long"),
    (5, "string_type"),
    (None, "string_type"),
], ids=["too-long", "int", "none"])
def test_invalid_name_is_rejected(value, error_type, assert_rejected):
    assert_rejected(RoleRequest, {"name": value}, "name", error_type)
