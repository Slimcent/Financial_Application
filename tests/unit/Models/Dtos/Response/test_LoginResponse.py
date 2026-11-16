"""LoginResponse (Models/Dtos/Response/LoginResponse.py)."""
from decimal import Decimal

import pytest

from Models.Dtos.Response.LoginResponse import LoginResponse

REQUIRED_FIELDS = ["user_id", "last_name", "first_name", "email", "role_id", "role_name"]
# Customers have an account type and a balance, staff a position: each is optional.
OPTIONAL_FIELDS = ["account_type_id", "account_type", "balance", "position"]
TEXT_FIELDS = ["last_name", "first_name", "email", "role_name", "account_type", "position"]


def test_valid_response_is_accepted(login_response_payload):
    assert LoginResponse(**login_response_payload).model_dump() == login_response_payload


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_required_field_is_rejected(login_response_payload, field, omit, assert_rejected):
    assert_rejected(LoginResponse, omit(login_response_payload, field), field, "missing")


@pytest.mark.parametrize("field", OPTIONAL_FIELDS)
def test_optional_field_defaults_to_none(login_response_payload, field, omit):
    assert getattr(LoginResponse(**omit(login_response_payload, field)), field) is None


def test_staff_login_has_a_position_and_no_account(login_response_payload):
    payload = {key: value for key, value in login_response_payload.items() if key not in OPTIONAL_FIELDS}
    response = LoginResponse(**payload, position="Teller")

    assert (response.position, response.account_type_id, response.account_type, response.balance) == \
        ("Teller", None, None, None)


@pytest.mark.parametrize("field", OPTIONAL_FIELDS)
def test_optional_field_accepts_none(login_response_payload, field):
    assert getattr(LoginResponse(**{**login_response_payload, field: None}), field) is None


def test_balance_is_kept_as_an_exact_decimal(login_response_payload, valid_money):
    raw, expected = valid_money
    balance = LoginResponse(**{**login_response_payload, "balance": raw}).balance

    assert isinstance(balance, Decimal)
    assert balance.as_tuple() == expected.as_tuple()


def test_invalid_balance_is_rejected(login_response_payload, invalid_optional_money, assert_rejected):
    assert_rejected(LoginResponse, {**login_response_payload, "balance": invalid_optional_money}, "balance")


def test_invalid_user_id_is_rejected(login_response_payload, invalid_guid, assert_rejected):
    assert_rejected(LoginResponse, {**login_response_payload, "user_id": invalid_guid}, "user_id")


def test_invalid_role_id_is_rejected(login_response_payload, invalid_integer, assert_rejected):
    assert_rejected(LoginResponse, {**login_response_payload, "role_id": invalid_integer}, "role_id")


def test_invalid_account_type_id_is_rejected(login_response_payload, invalid_optional_integer, assert_rejected):
    assert_rejected(LoginResponse, {**login_response_payload, "account_type_id": invalid_optional_integer},
                    "account_type_id")


@pytest.mark.parametrize("field", TEXT_FIELDS)
def test_text_field_must_be_text(login_response_payload, field, invalid_text, assert_rejected):
    assert_rejected(LoginResponse, {**login_response_payload, field: invalid_text}, field)


def test_serialised_as_json_values(login_response_payload):
    serialised = LoginResponse(**login_response_payload).model_dump(mode="json")

    assert serialised["user_id"] == str(login_response_payload["user_id"])
    assert serialised["balance"] == "100.00"
    assert serialised["position"] is None
