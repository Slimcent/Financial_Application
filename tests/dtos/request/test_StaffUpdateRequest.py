import pytest

from Dtos.Request.StaffUpdateRequest import StaffUpdateRequest

REQUIRED_FIELDS = ["last_name", "first_name", "email", "position"]
NAME_FIELDS = ["last_name", "first_name"]


def test_valid_update_request_is_accepted(staff_update_payload):
    assert StaffUpdateRequest(**staff_update_payload).model_dump() == staff_update_payload


def test_only_profile_details_are_accepted():
    assert set(StaffUpdateRequest.model_fields) == set(REQUIRED_FIELDS)


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_full_update_requires_every_field(staff_update_payload, field, omit, assert_rejected):
    assert_rejected(StaffUpdateRequest, omit(staff_update_payload, field), field, "missing")


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_blank_text_is_rejected(staff_update_payload, field, blank_value, assert_rejected):
    assert_rejected(StaffUpdateRequest, {**staff_update_payload, field: blank_value}, field)


@pytest.mark.parametrize("field", NAME_FIELDS)
def test_invalid_names_are_rejected(staff_update_payload, field, invalid_person_name, assert_rejected):
    assert_rejected(StaffUpdateRequest, {**staff_update_payload, field: invalid_person_name}, field)


def test_valid_email_is_trimmed_and_lowercased(staff_update_payload, valid_email):
    raw, expected = valid_email

    assert StaffUpdateRequest(**{**staff_update_payload, "email": raw}).email == expected


def test_invalid_email_is_rejected(staff_update_payload, invalid_email, assert_rejected):
    assert_rejected(StaffUpdateRequest, {**staff_update_payload, "email": invalid_email}, "email")


def test_position_length_limit(staff_update_payload, assert_rejected):
    assert_rejected(StaffUpdateRequest, {**staff_update_payload, "position": "x" * 101}, "position", "string_too_long")


@pytest.mark.parametrize("password", ["Str0ng#Pass", "", None], ids=["valid-password", "empty", "none"])
def test_supplying_a_password_raises_validation_error(staff_update_payload, password, assert_rejected):
    assert_rejected(StaffUpdateRequest, {**staff_update_payload, "password": password}, "password", "extra_forbidden")
