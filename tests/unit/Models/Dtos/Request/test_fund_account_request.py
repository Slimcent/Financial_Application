from decimal import Decimal

import pytest

from Models.Dtos.Request.fund_account_request import FundAccountRequest

REQUIRED_FIELDS = ["customer_id", "account_number", "amount", "transaction_type_id", "transaction_mode_id"]
IDENTIFIER_FIELDS = ["customer_id", "transaction_type_id", "transaction_mode_id"]


def test_valid_request_is_accepted(fund_account_payload):
    request = FundAccountRequest(**fund_account_payload)

    assert request.amount == Decimal("100.00")
    assert request.account_number == fund_account_payload["account_number"]


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_required_field_is_rejected(fund_account_payload, field, omit, assert_rejected):
    assert_rejected(FundAccountRequest, omit(fund_account_payload, field), field, "missing")


@pytest.mark.parametrize("field", IDENTIFIER_FIELDS)
def test_invalid_identifier_is_rejected(fund_account_payload, field, invalid_identifier, assert_rejected):
    assert_rejected(FundAccountRequest, {**fund_account_payload, field: invalid_identifier}, field)


def test_valid_account_number_is_accepted(fund_account_payload, valid_account_number):
    raw, expected = valid_account_number

    assert FundAccountRequest(**{**fund_account_payload, "account_number": raw}).account_number == expected


def test_invalid_account_number_is_rejected(fund_account_payload, invalid_account_number, assert_rejected):
    assert_rejected(FundAccountRequest, {**fund_account_payload, "account_number": invalid_account_number},
                    "account_number")


def test_valid_amount_is_accepted_as_two_place_decimal(fund_account_payload, valid_amount):
    raw, expected = valid_amount
    amount = FundAccountRequest(**{**fund_account_payload, "amount": raw}).amount

    assert isinstance(amount, Decimal)
    assert amount == expected
    assert amount.as_tuple().exponent == -2


def test_invalid_amount_is_rejected(fund_account_payload, invalid_amount, assert_rejected):
    assert_rejected(FundAccountRequest, {**fund_account_payload, "amount": invalid_amount}, "amount")
