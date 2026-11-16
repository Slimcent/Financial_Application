"""AccountTypeResponse (Models/Dtos/Response/AccountTypeResponse.py)."""
import pytest

from Models.Dtos.Response.AccountTypeResponse import AccountTypeResponse
from Services.Extensions.response_mappers import to_account_type_response

REQUIRED_FIELDS = ["account_type_id", "name"]


def test_valid_response_is_accepted(account_type_response_payload):
    assert AccountTypeResponse(**account_type_response_payload).model_dump() == account_type_response_payload


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_required_field_is_rejected(account_type_response_payload, field, omit, assert_rejected):
    assert_rejected(AccountTypeResponse, omit(account_type_response_payload, field), field, "missing")


def test_invalid_account_type_id_is_rejected(account_type_response_payload, invalid_integer, assert_rejected):
    assert_rejected(AccountTypeResponse, {**account_type_response_payload, "account_type_id": invalid_integer},
                    "account_type_id")


def test_name_must_be_text(account_type_response_payload, invalid_text, assert_rejected):
    assert_rejected(AccountTypeResponse, {**account_type_response_payload, "name": invalid_text}, "name")


def test_name_is_required_even_as_none(account_type_response_payload, assert_rejected):
    assert_rejected(AccountTypeResponse, {**account_type_response_payload, "name": None}, "name", "string_type")


def test_serialised_as_json_values(account_type_response_payload):
    assert AccountTypeResponse(**account_type_response_payload).model_dump_json() == \
        '{"account_type_id":1,"name":"Savings"}'


def test_account_type_entity_maps_to_a_valid_response(entity_graph):
    response = to_account_type_response(entity_graph.current)

    assert isinstance(response, AccountTypeResponse)
    assert (response.account_type_id, response.name) == (2, "Current")
