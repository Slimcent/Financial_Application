"""TransactionResponse and TransactionsResponse (Models/Dtos/Response/transaction_response.py)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from Models.Dtos.Response.transaction_response import TransactionResponse, TransactionsResponse
from Services.Extensions.response_mappers import to_transaction_response, to_transactions_response

TRANSACTION_REQUIRED_FIELDS = ["account_id", "account_number", "amount", "account_type_id", "account_type",
                               "transaction_type_id", "transaction_type", "transaction_mode_id", "transaction_mode",
                               "transaction_status_id", "transaction_status", "transaction_date"]
TRANSACTION_OPTIONAL_FIELDS = ["description", "sender_id", "sender"]
# TransactionsResponse adds the account owner.
TRANSACTIONS_REQUIRED_FIELDS = [*TRANSACTION_REQUIRED_FIELDS, "user_id", "last_name", "first_name", "email"]
TRANSACTIONS_OPTIONAL_FIELDS = [*TRANSACTION_OPTIONAL_FIELDS, "address", "customer_id", "staff_id"]

MODELS = {
    "TransactionResponse": (TransactionResponse, "transaction_response_payload", TRANSACTION_REQUIRED_FIELDS,
                            TRANSACTION_OPTIONAL_FIELDS),
    "TransactionsResponse": (TransactionsResponse, "transactions_response_payload", TRANSACTIONS_REQUIRED_FIELDS,
                             TRANSACTIONS_OPTIONAL_FIELDS),
}
IDENTIFIER_FIELDS = ["account_type_id", "transaction_type_id", "transaction_mode_id", "transaction_status_id"]
REQUIRED_CASES = [pytest.param(name, field, id=f"{name}-{field}") for name, (_, _, required, _) in MODELS.items()
                  for field in required]
OPTIONAL_CASES = [pytest.param(name, field, id=f"{name}-{field}") for name, (_, _, _, optional) in MODELS.items()
                  for field in optional]


@pytest.fixture(params=list(MODELS))
def transaction_model(request):
    """(model, valid payload, required fields, optional fields) for each transaction response."""
    return _model(request, request.param)


def _model(request, name):
    model, payload_fixture, required, optional = MODELS[name]
    return model, request.getfixturevalue(payload_fixture), required, optional


def test_valid_response_is_accepted(transaction_model):
    model, payload, _, _ = transaction_model

    assert model(**payload).model_dump() == payload


def test_every_field_is_either_required_or_optional(transaction_model):
    model, _, required, optional = transaction_model

    assert set(model.model_fields) == {*required, *optional}
    assert {name for name, field in model.model_fields.items() if field.is_required()} == set(required)


@pytest.mark.parametrize("name, field", REQUIRED_CASES)
def test_missing_required_field_is_rejected(request, name, field, omit, assert_rejected):
    model, payload, _, _ = _model(request, name)

    assert_rejected(model, omit(payload, field), field, "missing")


@pytest.mark.parametrize("name, field", OPTIONAL_CASES)
def test_optional_field_defaults_to_none(request, name, field, omit):
    model, payload, _, _ = _model(request, name)

    assert getattr(model(**omit(payload, field)), field) is None


def test_amount_is_kept_as_an_exact_decimal(transaction_model, valid_money):
    model, payload, _, _ = transaction_model
    raw, expected = valid_money
    amount = model(**{**payload, "amount": raw}).amount

    assert isinstance(amount, Decimal)
    assert amount.as_tuple() == expected.as_tuple()


def test_invalid_amount_is_rejected(transaction_model, invalid_money, assert_rejected):
    model, payload, _, _ = transaction_model

    assert_rejected(model, {**payload, "amount": invalid_money}, "amount")


@pytest.mark.parametrize("field", IDENTIFIER_FIELDS)
def test_invalid_identifier_is_rejected(transaction_model, field, invalid_integer, assert_rejected):
    model, payload, _, _ = transaction_model

    assert_rejected(model, {**payload, field: invalid_integer}, field)


def test_invalid_account_id_is_rejected(transaction_model, invalid_guid, assert_rejected):
    model, payload, _, _ = transaction_model

    assert_rejected(model, {**payload, "account_id": invalid_guid}, "account_id")


def test_invalid_sender_id_is_rejected(transaction_model, invalid_optional_guid, assert_rejected):
    model, payload, _, _ = transaction_model

    assert_rejected(model, {**payload, "sender_id": invalid_optional_guid}, "sender_id")


def test_invalid_transaction_date_is_rejected(transaction_model, invalid_datetime, assert_rejected):
    model, payload, _, _ = transaction_model

    assert_rejected(model, {**payload, "transaction_date": invalid_datetime}, "transaction_date")


def test_transaction_date_keeps_its_time_zone_and_microseconds(transaction_model):
    model, payload, _, _ = transaction_model
    west_africa = timezone(timedelta(hours=1))
    local_time = datetime(2026, 11, 15, 11, 45, 12, 123456, tzinfo=west_africa)

    transaction_date = model(**{**payload, "transaction_date": local_time}).transaction_date

    assert transaction_date == payload["transaction_date"]
    assert transaction_date.utcoffset() == timedelta(hours=1)
    assert transaction_date.microsecond == 123456


def test_description_may_be_none(transaction_model):
    model, payload, _, _ = transaction_model

    assert model(**{**payload, "description": None}).description is None


def test_serialised_as_json_values(transaction_model):
    model, payload, _, _ = transaction_model
    serialised = model(**payload).model_dump(mode="json")

    assert serialised["amount"] == "25.50"
    assert serialised["transaction_date"] == "2026-11-15T10:45:12.123456Z"
    assert serialised["account_id"] == str(payload["account_id"])
    assert serialised["sender_id"] == str(payload["sender_id"])


def test_owner_details_must_be_valid(transactions_response_payload, invalid_guid, assert_rejected):
    assert_rejected(TransactionsResponse, {**transactions_response_payload, "user_id": invalid_guid}, "user_id")


# ---------------------------------------------------------------------------
# Compatibility with the services (Services/Extensions/response_mappers.py)
# ---------------------------------------------------------------------------

def test_transaction_maps_to_a_valid_transaction_response(entity_graph):
    transaction = entity_graph.transaction

    response = to_transaction_response(transaction)

    assert isinstance(response, TransactionResponse)
    assert response.model_dump() == {
        "account_id": transaction.AccountId, "account_number": "2600000001", "amount": Decimal("25.50"),
        "account_type_id": 1, "account_type": "Savings", "transaction_type_id": 2, "transaction_type": "Transfer",
        "transaction_mode_id": 1, "transaction_mode": "Credit", "transaction_status_id": 2,
        "transaction_status": "Completed", "transaction_date": transaction.TransactionDate, "description": "Rent",
        "sender_id": entity_graph.ben.Id, "sender": "Ben Okafor"}


def test_transaction_maps_to_a_valid_transactions_response_with_its_owner(entity_graph):
    response = to_transactions_response(entity_graph.transaction)

    assert isinstance(response, TransactionsResponse)
    assert (response.user_id, response.first_name, response.last_name, response.email) == \
        (entity_graph.ada.Id, "Ada", "Lovelace", "example1@example.com")
    assert (response.customer_id, response.staff_id, response.address) == \
        (entity_graph.customer.Id, None, "1 Main Street")


def test_transaction_without_a_sender_maps_to_no_sender(entity_graph):
    transaction = entity_graph.transaction
    transaction.sender = None
    transaction.SenderId = None

    response = to_transaction_response(transaction)

    assert (response.sender_id, response.sender) == (None, None)
