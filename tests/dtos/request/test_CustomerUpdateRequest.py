import pytest

from Dtos.Request.CustomerUpdateRequest import CustomerUpdateRequest

REQUIRED_FIELDS = ["last_name", "first_name", "email", "address"]
NAME_FIELDS = ["last_name", "first_name"]


def test_valid_update_request_is_accepted(customer_update_payload):
    assert CustomerUpdateRequest(**customer_update_payload).model_dump() == customer_update_payload


def test_only_profile_details_are_accepted():
    assert set(CustomerUpdateRequest.model_fields) == set(REQUIRED_FIELDS)


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_full_update_requires_every_field(customer_update_payload, field, omit, assert_rejected):
    assert_rejected(CustomerUpdateRequest, omit(customer_update_payload, field), field, "missing")


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_blank_text_is_rejected(customer_update_payload, field, blank_value, assert_rejected):
    assert_rejected(CustomerUpdateRequest, {**customer_update_payload, field: blank_value}, field)


@pytest.mark.parametrize("field", NAME_FIELDS)
def test_invalid_names_are_rejected(customer_update_payload, field, invalid_person_name, assert_rejected):
    assert_rejected(CustomerUpdateRequest, {**customer_update_payload, field: invalid_person_name}, field)


def test_valid_email_is_trimmed_and_lowercased(customer_update_payload, valid_email):
    raw, expected = valid_email

    assert CustomerUpdateRequest(**{**customer_update_payload, "email": raw}).email == expected


def test_invalid_email_is_rejected(customer_update_payload, invalid_email, assert_rejected):
    assert_rejected(CustomerUpdateRequest, {**customer_update_payload, "email": invalid_email}, "email")


def test_address_length_limit(customer_update_payload, assert_rejected):
    assert_rejected(CustomerUpdateRequest, {**customer_update_payload, "address": "x" * 256}, "address",
                    "string_too_long")


@pytest.mark.parametrize("field, value", [
    ("password", "Str0ng#Pass"),
    ("password", None),
    ("account_type_id", 1),
])
def test_creation_only_fields_raise_validation_error(customer_update_payload, field, value, assert_rejected):
    assert_rejected(CustomerUpdateRequest, {**customer_update_payload, field: value}, field, "extra_forbidden")
