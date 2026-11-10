import pytest

from Dtos.Request.StaffCreateRequest import StaffCreateRequest

REQUIRED_FIELDS = ["last_name", "first_name", "email", "position", "password"]
NAME_FIELDS = ["last_name", "first_name"]


def test_valid_creation_request_is_accepted(staff_create_payload):
    assert StaffCreateRequest(**staff_create_payload).model_dump() == staff_create_payload


def test_position_is_trimmed(staff_create_payload):
    assert StaffCreateRequest(**{**staff_create_payload, "position": "  Branch Manager "}).position == "Branch Manager"


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_required_field_is_rejected(staff_create_payload, field, omit, assert_rejected):
    assert_rejected(StaffCreateRequest, omit(staff_create_payload, field), field, "missing")


def test_password_cannot_be_null(staff_create_payload, assert_rejected):
    assert_rejected(StaffCreateRequest, {**staff_create_payload, "password": None}, "password")


@pytest.mark.parametrize("field", NAME_FIELDS + ["email", "position", "password"])
def test_blank_text_is_rejected(staff_create_payload, field, blank_value, assert_rejected):
    assert_rejected(StaffCreateRequest, {**staff_create_payload, field: blank_value}, field)


@pytest.mark.parametrize("field", NAME_FIELDS)
def test_invalid_names_are_rejected(staff_create_payload, field, invalid_person_name, assert_rejected):
    assert_rejected(StaffCreateRequest, {**staff_create_payload, field: invalid_person_name}, field)


def test_invalid_email_is_rejected(staff_create_payload, invalid_email, assert_rejected):
    assert_rejected(StaffCreateRequest, {**staff_create_payload, "email": invalid_email}, "email")


def test_position_length_limit(staff_create_payload, assert_rejected):
    assert StaffCreateRequest(**{**staff_create_payload, "position": "x" * 100}).position == "x" * 100
    assert_rejected(StaffCreateRequest, {**staff_create_payload, "position": "x" * 101}, "position", "string_too_long")


def test_valid_password_is_accepted(staff_create_payload, valid_password):
    assert StaffCreateRequest(**{**staff_create_payload, "password": valid_password}).password == valid_password


def test_invalid_password_is_rejected(staff_create_payload, invalid_password, assert_rejected):
    assert_rejected(StaffCreateRequest, {**staff_create_payload, "password": invalid_password}, "password")


def test_password_is_hidden_from_repr(staff_create_payload):
    assert staff_create_payload["password"] not in repr(StaffCreateRequest(**staff_create_payload))
