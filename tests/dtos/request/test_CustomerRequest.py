import pytest

from Dtos.Request.CustomerRequest import CustomerRequest

REQUIRED_FIELDS = ["last_name", "first_name", "email", "address", "account_type_id", "password"]
NAME_FIELDS = ["last_name", "first_name"]


def test_valid_creation_request_is_accepted(customer_payload):
    assert CustomerRequest(**customer_payload).model_dump() == customer_payload


def test_text_fields_are_normalised(customer_payload):
    request = CustomerRequest(**{**customer_payload, "first_name": " Jane ", "email": " Jane.Doe@Example.COM ",
                                 "address": "  1 Main Street  "})

    assert (request.first_name, request.email, request.address) == ("Jane", "jane.doe@example.com", "1 Main Street")


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_required_field_is_rejected(customer_payload, field, omit, assert_rejected):
    assert_rejected(CustomerRequest, omit(customer_payload, field), field, "missing")


@pytest.mark.parametrize("field", ["account_type_id", "password"])
def test_creation_fields_cannot_be_null(customer_payload, field, assert_rejected):
    assert_rejected(CustomerRequest, {**customer_payload, field: None}, field)


@pytest.mark.parametrize("field", NAME_FIELDS + ["email", "address", "password"])
def test_blank_text_is_rejected(customer_payload, field, blank_value, assert_rejected):
    assert_rejected(CustomerRequest, {**customer_payload, field: blank_value}, field)


@pytest.mark.parametrize("field", NAME_FIELDS)
def test_invalid_names_are_rejected(customer_payload, field, invalid_person_name, assert_rejected):
    assert_rejected(CustomerRequest, {**customer_payload, field: invalid_person_name}, field)


def test_invalid_email_is_rejected(customer_payload, invalid_email, assert_rejected):
    assert_rejected(CustomerRequest, {**customer_payload, "email": invalid_email}, "email")


def test_invalid_account_type_id_is_rejected(customer_payload, invalid_identifier, assert_rejected):
    assert_rejected(CustomerRequest, {**customer_payload, "account_type_id": invalid_identifier}, "account_type_id")


def test_address_length_limit(customer_payload, assert_rejected):
    assert CustomerRequest(**{**customer_payload, "address": "x" * 255}).address == "x" * 255
    assert_rejected(CustomerRequest, {**customer_payload, "address": "x" * 256}, "address", "string_too_long")


def test_valid_password_is_accepted(customer_payload, valid_password):
    assert CustomerRequest(**{**customer_payload, "password": valid_password}).password == valid_password


def test_invalid_password_is_rejected(customer_payload, invalid_password, assert_rejected):
    assert_rejected(CustomerRequest, {**customer_payload, "password": invalid_password}, "password")


def test_password_is_hidden_from_repr(customer_payload):
    assert customer_payload["password"] not in repr(CustomerRequest(**customer_payload))
