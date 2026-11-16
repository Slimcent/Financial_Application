"""AccountsResponse (Models/Dtos/Response/AccountsResponse.py): one account."""
import uuid
from decimal import Decimal

import pytest

from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Services.Extensions.response_mappers import to_accounts_response

REQUIRED_FIELDS = ["account_id", "account_number", "balance", "account_type_id", "active"]
OPTIONAL_FIELDS = {"account_type": None}


def test_valid_response_is_accepted(accounts_response_payload):
    response = AccountsResponse(**accounts_response_payload)

    assert response.model_dump() == accounts_response_payload


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_required_field_is_rejected(accounts_response_payload, field, omit, assert_rejected):
    assert_rejected(AccountsResponse, omit(accounts_response_payload, field), field, "missing")


@pytest.mark.parametrize("field, default", OPTIONAL_FIELDS.items())
def test_optional_field_has_a_default(accounts_response_payload, field, default, omit):
    assert getattr(AccountsResponse(**omit(accounts_response_payload, field)), field) == default


def test_account_id_is_a_uuid(accounts_response_payload):
    response = AccountsResponse(**accounts_response_payload)

    assert isinstance(response.account_id, uuid.UUID)


def test_account_id_text_form_is_read_from_json(accounts_response_payload):
    # In Python the identifier must be a UUID (see invalid_guid); a JSON document carries it as text.
    json_text = AccountsResponse(**accounts_response_payload).model_dump_json()

    assert AccountsResponse.model_validate_json(json_text).account_id == accounts_response_payload["account_id"]


@pytest.mark.parametrize("active", [True, False])
def test_active_flag_is_kept(accounts_response_payload, active):
    assert AccountsResponse(**{**accounts_response_payload, "active": active}).active is active


@pytest.mark.parametrize("value", ["maybe", 2, None])
def test_invalid_active_flag_is_rejected(accounts_response_payload, value, assert_rejected):
    assert_rejected(AccountsResponse, {**accounts_response_payload, "active": value}, "active")


def test_balance_is_kept_as_an_exact_decimal(accounts_response_payload, valid_money):
    raw, expected = valid_money
    balance = AccountsResponse(**{**accounts_response_payload, "balance": raw}).balance

    assert isinstance(balance, Decimal)
    assert balance == expected
    assert balance.as_tuple() == expected.as_tuple()


def test_invalid_balance_is_rejected(accounts_response_payload, invalid_money, assert_rejected):
    assert_rejected(AccountsResponse, {**accounts_response_payload, "balance": invalid_money}, "balance")


def test_invalid_account_id_is_rejected(accounts_response_payload, invalid_guid, assert_rejected):
    assert_rejected(AccountsResponse, {**accounts_response_payload, "account_id": invalid_guid}, "account_id")


def test_invalid_account_type_id_is_rejected(accounts_response_payload, invalid_integer, assert_rejected):
    assert_rejected(AccountsResponse, {**accounts_response_payload, "account_type_id": invalid_integer},
                    "account_type_id")


@pytest.mark.parametrize("field", ["account_number", "account_type"])
def test_text_field_must_be_text(accounts_response_payload, field, invalid_text, assert_rejected):
    assert_rejected(AccountsResponse, {**accounts_response_payload, field: invalid_text}, field)


def test_serialised_as_json_values(accounts_response_payload):
    serialised = AccountsResponse(**accounts_response_payload).model_dump(mode="json")

    assert serialised == {"account_id": str(accounts_response_payload["account_id"]), "account_number": "2600000001",
                          "balance": "100.00", "account_type_id": 1, "account_type": "Savings", "active": True}


# ---------------------------------------------------------------------------
# Compatibility with the services (Services/Extensions/response_mappers.py)
# ---------------------------------------------------------------------------

def test_account_entity_maps_to_a_valid_response(entity_graph):
    account = entity_graph.savings_account

    response = to_accounts_response(account)

    assert isinstance(response, AccountsResponse)
    assert response.model_dump() == {"account_id": account.Id, "account_number": "2600000001",
                                     "balance": Decimal("100.00"), "account_type_id": 1, "account_type": "Savings",
                                     "active": True}


def test_deactivated_account_maps_to_an_inactive_response(entity_graph):
    account = entity_graph.savings_account
    account.Active = False

    assert to_accounts_response(account).active is False


def test_mapped_balance_is_the_entity_decimal(entity_graph):
    assert to_accounts_response(entity_graph.savings_account).balance is entity_graph.savings_account.Balance


def test_account_type_given_explicitly_is_used(entity_graph):
    # A just created account has no loaded account_type: the service passes the one it loaded.
    account = entity_graph.savings_account
    account.account_type = None

    assert to_accounts_response(account, entity_graph.savings).account_type == "Savings"


def test_account_without_an_account_type_maps_to_no_type_name(entity_graph):
    account = entity_graph.savings_account
    account.account_type = None

    assert to_accounts_response(account).account_type is None
