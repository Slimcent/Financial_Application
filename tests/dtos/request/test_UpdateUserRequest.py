import pytest

from Dtos.Request.UpdateUserRequest import UpdateUserRequest

REQUIRED_FIELDS = ["last_name", "first_name", "email"]
NAME_FIELDS = ["last_name", "first_name"]


def test_valid_request_is_accepted(update_user_payload):
    assert UpdateUserRequest(**update_user_payload).model_dump() == update_user_payload


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_required_field_is_rejected(update_user_payload, field, omit, assert_rejected):
    assert_rejected(UpdateUserRequest, omit(update_user_payload, field), field, "missing")


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_blank_text_is_rejected(update_user_payload, field, blank_value, assert_rejected):
    assert_rejected(UpdateUserRequest, {**update_user_payload, field: blank_value}, field)


@pytest.mark.parametrize("field", NAME_FIELDS)
def test_invalid_names_are_rejected(update_user_payload, field, invalid_person_name, assert_rejected):
    assert_rejected(UpdateUserRequest, {**update_user_payload, field: invalid_person_name}, field)


def test_valid_email_is_trimmed_and_lowercased(update_user_payload, valid_email):
    raw, expected = valid_email

    assert UpdateUserRequest(**{**update_user_payload, "email": raw}).email == expected


def test_invalid_email_is_rejected(update_user_payload, invalid_email, assert_rejected):
    assert_rejected(UpdateUserRequest, {**update_user_payload, "email": invalid_email}, "email")


@pytest.mark.parametrize("field, value", [("password", "Str0ng#Pass"), ("role_id", 1)])
def test_fields_outside_profile_details_are_rejected(update_user_payload, field, value, assert_rejected):
    assert field not in UpdateUserRequest.model_fields
    assert_rejected(UpdateUserRequest, {**update_user_payload, field: value}, field, "extra_forbidden")
