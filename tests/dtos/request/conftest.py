"""Shared fixtures for the request-model validation tests.

These tests only exercise the pydantic request models in Dtos/Request.
They must not import services, repositories, database connections or other infrastructure.
"""
from decimal import Decimal

import pytest
from pydantic import ValidationError

VALID_ACCOUNT_NUMBER = "2606387058"
OTHER_ACCOUNT_NUMBER = "2684681945"
VALID_PASSWORD = "Str0ng#Pass"

# An email address of exactly 254 characters (the maximum allowed): 64-char local part, 189-char domain.
LONGEST_VALID_EMAIL = f"{'a' * 64}@{'b' * 63}.{'c' * 63}.{'d' * 57}.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def assert_rejected():
    """Assert that building `model` from `payload` raises a ValidationError for `field`.

    `field=None` expects a model-level error (e.g. a model_validator). When `error_type` is given,
    the error reported for that location must have that pydantic error type.
    """

    def _assert_rejected(model, payload, field=None, error_type=None):
        with pytest.raises(ValidationError) as exc_info:
            model(**payload)

        expected_loc = (field,) if field else ()
        errors_at_loc = [error for error in exc_info.value.errors() if error["loc"] == expected_loc]
        assert errors_at_loc, f"expected an error at {expected_loc}, got {exc_info.value.errors()}"

        if error_type is not None:
            assert error_type in [error["type"] for error in errors_at_loc], exc_info.value.errors()

        return exc_info.value

    return _assert_rejected


@pytest.fixture
def omit():
    """Return a copy of `payload` without `field`."""

    def _omit(payload, field):
        return {key: value for key, value in payload.items() if key != field}

    return _omit


# ---------------------------------------------------------------------------
# Valid payloads (a fresh dict per test)
# ---------------------------------------------------------------------------

@pytest.fixture
def user_payload():
    return {"last_name": "Doe", "first_name": "Jane", "email": "jane.doe@example.com", "role_id": 1,
            "password": VALID_PASSWORD}


@pytest.fixture
def update_user_payload():
    return {"last_name": "Doe", "first_name": "Jane", "email": "jane.doe@example.com"}


@pytest.fixture
def customer_payload():
    return {"last_name": "Doe", "first_name": "Jane", "email": "jane.doe@example.com", "address": "1 Main Street",
            "account_type_id": 1, "password": VALID_PASSWORD}


@pytest.fixture
def customer_update_payload():
    return {"last_name": "Doe", "first_name": "Jane", "email": "jane.doe@example.com", "address": "1 Main Street"}


@pytest.fixture
def staff_create_payload():
    return {"last_name": "Smith", "first_name": "John", "email": "john.smith@example.com", "position": "Teller",
            "password": VALID_PASSWORD}


@pytest.fixture
def staff_update_payload():
    return {"last_name": "Smith", "first_name": "John", "email": "john.smith@example.com", "position": "Teller"}


@pytest.fixture
def account_type_payload():
    return {"name": "Savings"}


@pytest.fixture
def role_payload():
    return {"name": "Customer"}


@pytest.fixture
def fund_account_payload():
    return {"customer_id": 1, "account_number": VALID_ACCOUNT_NUMBER, "amount": "100.00", "transaction_type_id": 1,
            "transaction_mode_id": 1}


@pytest.fixture
def transaction_payload():
    return {"user_id": 1, "account_id": 1, "account_number": VALID_ACCOUNT_NUMBER, "amount": "100.00",
            "transaction_type_id": 1, "transaction_mode_id": 1, "transaction_status_id": 2}


@pytest.fixture
def user_transactions_payload():
    return {"user_id": 1}


@pytest.fixture
def funds_transfer_payload():
    return {"amount": "300.00", "sender_account_number": VALID_ACCOUNT_NUMBER,
            "receiver_account_number": OTHER_ACCOUNT_NUMBER}


# ---------------------------------------------------------------------------
# Shared validator cases (parametrized fixtures: each test using one runs once per case)
# ---------------------------------------------------------------------------

@pytest.fixture(params=["", "   ", "\t\n "], ids=["empty", "spaces", "tabs-newlines"])
def blank_value(request):
    return request.param


@pytest.fixture(params=[
    ("Jane", "Jane"),
    ("  Jane  ", "Jane"),
    ("O'Brien", "O'Brien"),
    ("D’Angelo", "D’Angelo"),
    ("Mary-Jane", "Mary-Jane"),
    ("van der Berg", "van der Berg"),
    ("St. John", "St. John"),
    ("J.R.R.", "J.R.R."),
    ("José", "José"),
    ("Jose\u0301", "José"),            # decomposed accent is normalised to NFC
    ("Nguyễn", "Nguyễn"),
    ("李", "李"),
    ("محمد", "محمد"),
    ("अमित", "अमित"),                  # combining vowel signs
    ("x" * 100, "x" * 100),            # maximum length
], ids=lambda case: repr(case[0])[:20])
def valid_person_name(request):
    return request.param


@pytest.fixture(params=[
    pytest.param("J4ne", id="digit"),
    pytest.param("-Jane", id="leading-hyphen"),
    pytest.param("Jane-", id="trailing-hyphen"),
    pytest.param("Jane  Doe", id="double-space"),
    pytest.param("Jane_Doe", id="underscore"),
    pytest.param("Smith, Jr.", id="comma"),
    pytest.param("<script>", id="markup"),
    pytest.param("\u0301Jose", id="leading-combining-mark"),
    pytest.param("x" * 101, id="too-long"),
    pytest.param(123, id="int"),
    pytest.param(None, id="none"),
])
def invalid_person_name(request):
    return request.param


@pytest.fixture(params=[
    ("jane@example.com", "jane@example.com"),
    ("  Jane.Doe+Bank@Example.COM ", "jane.doe+bank@example.com"),
    ("\tJANE@EXAMPLE.COM\n", "jane@example.com"),
    ("o'neil@sub.domain.org", "o'neil@sub.domain.org"),
    ("a@b.co", "a@b.co"),
    (LONGEST_VALID_EMAIL, LONGEST_VALID_EMAIL),
], ids=["plain", "trim-and-lowercase", "tab-newline-uppercase", "apostrophe-subdomain", "shortest", "254-chars"])
def valid_email(request):
    return request.param


@pytest.fixture(params=[
    pytest.param("plain-address", id="no-at"),
    pytest.param("jane@", id="no-domain"),
    pytest.param("@example.com", id="no-local-part"),
    pytest.param("jane@example", id="no-tld"),
    pytest.param("jane@@example.com", id="double-at"),
    pytest.param("jane@example..com", id="double-dot-domain"),
    pytest.param(".jane@example.com", id="leading-dot"),
    pytest.param("jane.@example.com", id="trailing-dot-local"),
    pytest.param("ja..ne@example.com", id="double-dot-local"),
    pytest.param("ja ne@example.com", id="inner-space"),
    pytest.param("jane@-example.com", id="label-leading-hyphen"),
    pytest.param("jane@example-.com", id="label-trailing-hyphen"),
    pytest.param("jane@example.c", id="one-letter-tld"),
    pytest.param("jane@example.c0m", id="digit-in-tld"),
    pytest.param(f"{'a' * 65}@example.com", id="local-part-too-long"),
    pytest.param(LONGEST_VALID_EMAIL.replace("d" * 57, "d" * 58), id="255-chars"),
    pytest.param(12345, id="int"),
    pytest.param(None, id="none"),
])
def invalid_email(request):
    return request.param


@pytest.fixture(params=[1, 2_147_483_647], ids=["one", "mysql-int-max"])
def valid_identifier(request):
    return request.param


@pytest.fixture(params=[
    pytest.param(0, id="zero"),
    pytest.param(-1, id="negative"),
    pytest.param(2_147_483_648, id="above-mysql-int-max"),
    pytest.param("1", id="numeric-string"),
    pytest.param(1.0, id="float"),
    pytest.param(True, id="bool"),
    pytest.param(None, id="none"),
])
def invalid_identifier(request):
    return request.param


@pytest.fixture(params=[
    (VALID_ACCOUNT_NUMBER, VALID_ACCOUNT_NUMBER),
    (f"  {VALID_ACCOUNT_NUMBER} ", VALID_ACCOUNT_NUMBER),
    ("0000000000", "0000000000"),
], ids=["digits", "surrounding-whitespace", "all-zeros"])
def valid_account_number(request):
    return request.param


_INVALID_ACCOUNT_NUMBERS = [
    pytest.param("260638705", id="nine-digits"),
    pytest.param("26063870581", id="eleven-digits"),
    pytest.param("26063870a8", id="letter"),
    pytest.param("2606-38705", id="hyphen"),
    pytest.param("26063 8705", id="inner-space"),
    pytest.param("", id="empty"),
    pytest.param("   ", id="whitespace-only"),
    pytest.param("２６０６３８７０５８", id="full-width-digits"),
    pytest.param(2606387058, id="int"),
    pytest.param(None, id="none"),
]


@pytest.fixture(params=_INVALID_ACCOUNT_NUMBERS)
def invalid_account_number(request):
    """Invalid values for a required account number."""
    return request.param


@pytest.fixture(params=[case for case in _INVALID_ACCOUNT_NUMBERS if case.values[0] is not None])
def invalid_account_number_filter(request):
    """Invalid values for an optional account-number filter (None is allowed there: it means 'no filter')."""
    return request.param


@pytest.fixture(params=[
    (1, Decimal("1.00")),
    (Decimal("250.75"), Decimal("250.75")),
    ("0.01", Decimal("0.01")),
    ("10.5", Decimal("10.50")),
    ("1.500", Decimal("1.50")),
    (" 12.30 ", Decimal("12.30")),
    ("1e2", Decimal("100.00")),
    ("99999999.99", Decimal("99999999.99")),
], ids=["int", "decimal", "smallest", "one-place", "trailing-zero", "whitespace", "exponent", "db-maximum"])
def valid_amount(request):
    return request.param


@pytest.fixture(params=[
    pytest.param(0, id="zero-int"),
    pytest.param("0.00", id="zero-string"),
    pytest.param(Decimal("0"), id="zero-decimal"),
    pytest.param(-1, id="negative-int"),
    pytest.param("-0.01", id="negative-string"),
    pytest.param(Decimal("-5.00"), id="negative-decimal"),
    pytest.param(10.5, id="float"),
    pytest.param(100.0, id="whole-float"),
    pytest.param(0.1, id="small-float"),
    pytest.param("0.001", id="three-places-string"),
    pytest.param("10.999", id="three-places-rounding"),
    pytest.param(Decimal("1.005"), id="three-places-decimal"),
    pytest.param("100000000", id="above-db-maximum"),
    pytest.param("1e9", id="exponent-above-db-maximum"),
    pytest.param(True, id="bool"),
    pytest.param("NaN", id="nan"),
    pytest.param("Infinity", id="infinity"),
    pytest.param("abc", id="non-numeric"),
    pytest.param("", id="empty"),
    pytest.param(None, id="none"),
])
def invalid_amount(request):
    return request.param


@pytest.fixture(params=[
    "8chars!!",                  # minimum length
    "a" * 72,                    # maximum bytes
    "é" * 36,                    # 72 bytes of multi-byte characters
    "  spaced pass  ",           # surrounding whitespace is part of the password
], ids=["min-length", "72-bytes", "72-bytes-multibyte", "surrounding-spaces"])
def valid_password(request):
    return request.param


@pytest.fixture(params=[
    pytest.param("Sh0rt!!", id="seven-chars"),
    pytest.param(" " * 8, id="spaces-only"),
    pytest.param("\t" * 8, id="tabs-only"),
    pytest.param("a" * 73, id="73-bytes"),
    pytest.param("é" * 37, id="74-bytes-multibyte"),
    pytest.param(12345678, id="int"),
    pytest.param(None, id="none"),
])
def invalid_password(request):
    return request.param


@pytest.fixture(params=[
    (None, None),
    ("Rent for May", "Rent for May"),
    ("  rent  ", "rent"),
    ("", None),
    ("   ", None),
    ("x" * 255, "x" * 255),
], ids=["none", "text", "trimmed", "empty-to-none", "whitespace-to-none", "max-length"])
def valid_description(request):
    return request.param


@pytest.fixture(params=[
    pytest.param("x" * 256, id="too-long"),
    pytest.param(5, id="int"),
    pytest.param(b"rent", id="bytes"),
])
def invalid_description(request):
    return request.param


@pytest.fixture(params=[
    pytest.param(0, id="zero"),
    pytest.param(-1, id="negative"),
    pytest.param("2", id="numeric-string"),
    pytest.param(2.0, id="float"),
    pytest.param(True, id="bool"),
    pytest.param(None, id="none"),
])
def invalid_page(request):
    return request.param


@pytest.fixture(params=[
    pytest.param(0, id="zero"),
    pytest.param(-5, id="negative"),
    pytest.param(51, id="above-maximum"),
    pytest.param(100, id="far-above-maximum"),
    pytest.param("10", id="numeric-string"),
    pytest.param(10.0, id="float"),
    pytest.param(True, id="bool"),
    pytest.param(None, id="none"),
])
def invalid_page_size(request):
    return request.param
