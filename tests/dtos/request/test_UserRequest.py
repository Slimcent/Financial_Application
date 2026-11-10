import pytest

from Dtos.Request.UserRequest import UserRequest

REQUIRED_FIELDS = ["last_name", "first_name", "email", "role_id", "password"]
NAME_FIELDS = ["last_name", "first_name"]


def test_valid_request_is_accepted(user_payload):
    request = UserRequest(**user_payload)

    assert request.model_dump() == user_payload


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_required_field_is_rejected(user_payload, field, omit, assert_rejected):
    assert_rejected(UserRequest, omit(user_payload, field), field, "missing")


@pytest.mark.parametrize("field", NAME_FIELDS + ["email", "password"])
def test_blank_text_is_rejected(user_payload, field, blank_value, assert_rejected):
    assert_rejected(UserRequest, {**user_payload, field: blank_value}, field)


@pytest.mark.parametrize("field", NAME_FIELDS)
def test_valid_names_are_accepted_and_normalised(user_payload, field, valid_person_name):
    raw, expected = valid_person_name

    assert getattr(UserRequest(**{**user_payload, field: raw}), field) == expected


@pytest.mark.parametrize("field", NAME_FIELDS)
def test_invalid_names_are_rejected(user_payload, field, invalid_person_name, assert_rejected):
    assert_rejected(UserRequest, {**user_payload, field: invalid_person_name}, field)


def test_valid_email_is_trimmed_and_lowercased(user_payload, valid_email):
    raw, expected = valid_email

    assert UserRequest(**{**user_payload, "email": raw}).email == expected


def test_invalid_email_is_rejected(user_payload, invalid_email, assert_rejected):
    assert_rejected(UserRequest, {**user_payload, "email": invalid_email}, "email")


def test_valid_role_id_is_accepted(user_payload, valid_identifier):
    assert UserRequest(**{**user_payload, "role_id": valid_identifier}).role_id == valid_identifier


def test_invalid_role_id_is_rejected(user_payload, invalid_identifier, assert_rejected):
    assert_rejected(UserRequest, {**user_payload, "role_id": invalid_identifier}, "role_id")


def test_valid_password_is_kept_verbatim(user_payload, valid_password):
    assert UserRequest(**{**user_payload, "password": valid_password}).password == valid_password


def test_invalid_password_is_rejected(user_payload, invalid_password, assert_rejected):
    assert_rejected(UserRequest, {**user_payload, "password": invalid_password}, "password")


def test_password_is_hidden_from_repr(user_payload):
    assert user_payload["password"] not in repr(UserRequest(**user_payload))
