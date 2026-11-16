"""RoleResponse (Models/Dtos/Response/RoleResponse.py)."""
import pytest

from Models.Dtos.Response.RoleResponse import RoleResponse

REQUIRED_FIELDS = ["role_id", "name"]


def test_valid_response_is_accepted(role_response_payload):
    assert RoleResponse(**role_response_payload).model_dump() == role_response_payload


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_required_field_is_rejected(role_response_payload, field, omit, assert_rejected):
    assert_rejected(RoleResponse, omit(role_response_payload, field), field, "missing")


def test_invalid_role_id_is_rejected(role_response_payload, invalid_integer, assert_rejected):
    assert_rejected(RoleResponse, {**role_response_payload, "role_id": invalid_integer}, "role_id")


def test_name_must_be_text(role_response_payload, invalid_text, assert_rejected):
    assert_rejected(RoleResponse, {**role_response_payload, "name": invalid_text}, "name")


def test_role_id_must_be_an_integer_not_its_text_form(role_response_payload, assert_rejected):
    assert_rejected(RoleResponse, {**role_response_payload, "role_id": "2"}, "role_id", "int_type")


def test_role_id_is_read_from_json_as_a_number(role_response_payload):
    assert RoleResponse.model_validate_json('{"role_id": 2, "name": "Staff"}').role_id == 2


def test_serialised_as_json_values(role_response_payload):
    assert RoleResponse(**role_response_payload).model_dump_json() == '{"role_id":1,"name":"Customer"}'


def test_role_entity_values_make_a_valid_response(entity_graph):
    # No service returns roles yet; the response holds a Roles row (Id, Name).
    role = entity_graph.staff_role

    assert RoleResponse(role_id=role.Id, name=role.Name).model_dump() == {"role_id": 2, "name": "Staff"}
