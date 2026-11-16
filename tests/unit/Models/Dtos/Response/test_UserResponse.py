"""UserResponse (Models/Dtos/Response/UserResponse.py): a user, with its customer or staff details."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Response.UserResponse import UserResponse
from Services.Extensions.response_mappers import to_customer_response, to_staff_response, to_user_response

# Every field is optional: a response carries the customer details or the staff details, not both.
FIELDS_WITHOUT_DEFAULT_VALUE = ["user_id", "customer_id", "staff_id", "last_name", "first_name", "email", "address",
                                "position", "role_id", "role_name", "active", "created_at"]
TEXT_FIELDS = ["last_name", "first_name", "email", "address", "position", "role_name"]
GUID_FIELDS = ["user_id", "customer_id", "staff_id"]


def test_valid_response_is_accepted(user_response_payload, accounts_response_payload):
    response = UserResponse(**user_response_payload)

    assert response.model_dump() == {**user_response_payload, "accounts": [accounts_response_payload]}


def test_every_field_is_optional():
    response = UserResponse()

    assert all(getattr(response, field) is None for field in FIELDS_WITHOUT_DEFAULT_VALUE)
    assert response.accounts == []


def test_accounts_default_is_not_shared_between_responses():
    first, second = UserResponse(), UserResponse()
    first.accounts.append("changed")

    assert second.accounts == []


def test_accounts_are_validated_as_account_responses(user_response_payload, accounts_response_payload):
    account = UserResponse(**user_response_payload).accounts[0]

    assert isinstance(account, AccountsResponse)
    assert account.balance == Decimal("100.00")


def test_account_responses_are_kept_as_given(user_response_payload, accounts_response_payload):
    account = AccountsResponse(**accounts_response_payload)

    assert UserResponse(**{**user_response_payload, "accounts": [account]}).accounts[0] is account


def test_invalid_account_is_reported_at_its_position(user_response_payload, accounts_response_payload):
    accounts = [accounts_response_payload, {**accounts_response_payload, "balance": "abc"}]

    with pytest.raises(ValidationError) as exc_info:
        UserResponse(**{**user_response_payload, "accounts": accounts})

    assert [item["loc"] for item in exc_info.value.errors()] == [("accounts", 1, "balance")]


def test_accounts_must_be_a_list(user_response_payload, assert_rejected):
    assert_rejected(UserResponse, {**user_response_payload, "accounts": None}, "accounts", "list_type")


@pytest.mark.parametrize("field", GUID_FIELDS)
def test_invalid_identifier_is_rejected(user_response_payload, field, invalid_optional_guid, assert_rejected):
    assert_rejected(UserResponse, {**user_response_payload, field: invalid_optional_guid}, field)


def test_invalid_role_id_is_rejected(user_response_payload, invalid_optional_integer, assert_rejected):
    assert_rejected(UserResponse, {**user_response_payload, "role_id": invalid_optional_integer}, "role_id")


def test_role_name_is_not_a_valid_role_id(user_response_payload, assert_rejected):
    # role_id was typed as text before the conversion; it is the Roles.Id integer.
    assert_rejected(UserResponse, {**user_response_payload, "role_id": "Customer"}, "role_id", "int_type")


@pytest.mark.parametrize("field", TEXT_FIELDS)
def test_text_field_must_be_text(user_response_payload, field, invalid_text, assert_rejected):
    assert_rejected(UserResponse, {**user_response_payload, field: invalid_text}, field)


@pytest.mark.parametrize("value", ["maybe", 2, "active"])
def test_invalid_active_flag_is_rejected(user_response_payload, value, assert_rejected):
    assert_rejected(UserResponse, {**user_response_payload, "active": value}, "active")


def test_created_at_is_read_from_iso_text_with_its_time_zone(user_response_payload):
    created_at = UserResponse(**{**user_response_payload, "created_at": "2026-11-15T09:30:00Z"}).created_at

    assert created_at == datetime(2026, 11, 15, 9, 30, tzinfo=timezone.utc)
    assert created_at.utcoffset().total_seconds() == 0


def test_invalid_created_at_is_rejected(user_response_payload, invalid_datetime, assert_rejected):
    assert_rejected(UserResponse, {**user_response_payload, "created_at": invalid_datetime}, "created_at")


def test_serialised_as_json_values(user_response_payload):
    serialised = UserResponse(**user_response_payload).model_dump(mode="json")

    assert serialised["user_id"] == str(user_response_payload["user_id"])
    assert serialised["created_at"] == "2026-11-15T09:30:00Z"
    assert serialised["accounts"][0]["balance"] == "100.00"
    assert serialised["staff_id"] is None


# ---------------------------------------------------------------------------
# Compatibility with the services (Services/Extensions/response_mappers.py)
# ---------------------------------------------------------------------------

def test_customer_maps_to_a_valid_response(entity_graph):
    response = to_customer_response(entity_graph.customer)

    assert isinstance(response, UserResponse)
    assert (response.user_id, response.customer_id, response.staff_id) == \
        (entity_graph.ada.Id, entity_graph.customer.Id, None)
    assert (response.address, response.position, response.role_id, response.role_name) == \
        ("1 Main Street", None, 1, "Customer")
    assert (response.active, response.created_at) == (True, entity_graph.ada.CreatedAt)
    # accounts ordered by account type, balances kept as Decimals
    assert [(account.account_number, account.balance) for account in response.accounts] == \
        [("2600000001", Decimal("100.00")), ("2600000002", Decimal("50.00"))]


def test_staff_maps_to_a_valid_response(entity_graph):
    response = to_staff_response(entity_graph.staff)

    assert (response.user_id, response.staff_id, response.customer_id) == \
        (entity_graph.dee.Id, entity_graph.staff.Id, None)
    assert (response.position, response.address, response.role_name, response.active, response.accounts) == \
        ("Teller", None, "Staff", False, [])


def test_user_without_a_loaded_role_keeps_its_role_id(entity_graph):
    response = to_user_response(entity_graph.ben, None)

    assert (response.role_id, response.role_name) == (1, None)


def test_mapped_response_round_trips_through_json(entity_graph):
    response = to_customer_response(entity_graph.customer)

    assert UserResponse.model_validate_json(response.model_dump_json()) == response
