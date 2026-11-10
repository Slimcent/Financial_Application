import pytest

from Dtos.Request.AccountTypeRequest import AccountTypeRequest


@pytest.mark.parametrize("raw, expected", [
    ("Savings", "Savings"),
    ("  Fixed Deposit (12M) ", "Fixed Deposit (12M)"),
    ("x" * 50, "x" * 50),
], ids=["simple", "trimmed", "max-length"])
def test_valid_name_is_accepted(raw, expected):
    assert AccountTypeRequest(name=raw).name == expected


def test_missing_name_is_rejected(assert_rejected):
    assert_rejected(AccountTypeRequest, {}, "name", "missing")


def test_blank_name_is_rejected(blank_value, assert_rejected):
    assert_rejected(AccountTypeRequest, {"name": blank_value}, "name")


@pytest.mark.parametrize("value, error_type", [
    ("x" * 51, "string_too_long"),
    (5, "string_type"),
    (None, "string_type"),
], ids=["too-long", "int", "none"])
def test_invalid_name_is_rejected(value, error_type, assert_rejected):
    assert_rejected(AccountTypeRequest, {"name": value}, "name", error_type)
