"""Shared configuration from Models/Dtos/Response/base_response.py, verified through every response model."""
import importlib
import inspect
import typing
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from Models.Dtos.Response.AccountResponse import AccountResponse
from Models.Dtos.Response.AccountTypeResponse import AccountTypeResponse
from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Response.LoginResponse import LoginResponse
from Models.Dtos.Response.RoleResponse import RoleResponse
from Models.Dtos.Response.UserResponse import UserResponse
from Models.Dtos.Response.base_response import BaseResponse, GuidId, IntegerId, Money
from Models.Dtos.Response.paged_response import PagedResponse
from Models.Dtos.Response.transaction_response import TransactionResponse, TransactionsResponse

# Every response model with the fixture that provides a valid payload.
RESPONSE_MODELS = [
    (AccountResponse, "account_response_payload"),
    (AccountsResponse, "accounts_response_payload"),
    (AccountTypeResponse, "account_type_response_payload"),
    (LoginResponse, "login_response_payload"),
    (RoleResponse, "role_response_payload"),
    (UserResponse, "user_response_payload"),
    (PagedResponse, "paged_response_payload"),
    (TransactionResponse, "transaction_response_payload"),
    (TransactionsResponse, "transactions_response_payload"),
]
RESPONSE_MODEL_IDS = [model.__name__ for model, _ in RESPONSE_MODELS]
RESPONSE_PACKAGE_DIR = Path(inspect.getfile(BaseResponse)).parent
RESPONSE_PACKAGE = BaseResponse.__module__.rsplit(".", 1)[0]  # e.g. "Models.Dtos.Response"

# Money fields: Decimal, as the entities store money (DECIMAL columns) and the requests accept it.
MONEY_FIELDS = [
    (AccountsResponse, "balance"),
    (AccountResponse, "balance"),
    (AccountResponse, "total_balance"),
    (LoginResponse, "balance"),
    (TransactionResponse, "amount"),
    (TransactionsResponse, "amount"),
]


@pytest.fixture(params=RESPONSE_MODELS, ids=RESPONSE_MODEL_IDS)
def model_and_payload(request):
    model, payload_fixture = request.param
    return model, request.getfixturevalue(payload_fixture)


def _discover_response_models():
    models = set()
    for path in RESPONSE_PACKAGE_DIR.glob("*.py"):
        if path.stem == "__init__":
            continue
        module = importlib.import_module(f"{RESPONSE_PACKAGE}.{path.stem}")
        for _, member in inspect.getmembers(module, inspect.isclass):
            if issubclass(member, BaseModel) and member.__module__ == module.__name__ and member is not BaseResponse:
                models.add(member)
    return models


def _types_in(annotation):
    """Every type an annotation names, e.g. Optional[List[X]] -> {NoneType, list, X}."""
    found = {annotation}
    for argument in typing.get_args(annotation):
        found |= _types_in(argument)
    origin = typing.get_origin(annotation)
    if origin is not None:
        found.add(origin)
    return found


def test_every_response_model_uses_the_shared_base_and_is_covered_here():
    discovered = _discover_response_models()

    assert all(issubclass(model, BaseResponse) for model in discovered)
    assert discovered == {model for model, _ in RESPONSE_MODELS}


def test_valid_payload_is_accepted(model_and_payload):
    model, payload = model_and_payload

    assert isinstance(model(**payload), model)


def test_unknown_field_is_rejected(model_and_payload, assert_rejected):
    model, payload = model_and_payload

    assert_rejected(model, {**payload, "unexpected_field": "value"}, "unexpected_field", "extra_forbidden")


def test_positional_arguments_are_rejected(model_and_payload):
    model, payload = model_and_payload

    with pytest.raises(TypeError):
        model(*payload.values())


def test_validation_error_is_a_value_error(role_response_payload):
    # main.py reports invalid models through its `except ValueError` handler.
    with pytest.raises(ValueError):
        RoleResponse(**{**role_response_payload, "role_id": "not-a-number"})


def test_response_round_trips_through_python_values(model_and_payload):
    model, payload = model_and_payload
    response = model(**payload)

    assert model.model_validate(response.model_dump()) == response


def test_response_round_trips_through_json(model_and_payload):
    model, payload = model_and_payload
    response = model(**payload)

    assert model.model_validate_json(response.model_dump_json()) == response


def test_vars_lists_every_field(model_and_payload):
    # The Application layer prints and converts responses with vars().
    model, payload = model_and_payload

    assert set(vars(model(**payload))) == set(model.model_fields)


@pytest.mark.parametrize("model", [model for model, _ in RESPONSE_MODELS], ids=RESPONSE_MODEL_IDS)
def test_no_field_is_a_float(model):
    for name, field in model.model_fields.items():
        assert float not in _types_in(field.annotation), f"{model.__name__}.{name} is a float"


@pytest.mark.parametrize("model, field", MONEY_FIELDS, ids=[f"{model.__name__}.{field}" for model, field in MONEY_FIELDS])
def test_money_fields_are_decimals(model, field):
    assert Decimal in _types_in(model.model_fields[field].annotation)


@pytest.mark.parametrize("model, field", MONEY_FIELDS, ids=[f"{model.__name__}.{field}" for model, field in MONEY_FIELDS])
def test_money_is_serialised_as_exact_text(request, model, field):
    payload = request.getfixturevalue(dict(RESPONSE_MODELS)[model])
    response = model(**{**payload, field: Decimal("1234567.05")})

    assert response.model_dump(mode="json")[field] == "1234567.05"
    assert f'"{field}":"1234567.05"' in response.model_dump_json()


# ---------------------------------------------------------------------------
# Identifiers have the type of their key column; money is a Decimal that also takes floats
# ---------------------------------------------------------------------------

GUID = uuid.UUID("3f2b8c9e-6d4a-4e1f-9b7c-2a5d8e0f1c34")
# Values of a neighbouring type that lax validation would convert; identifiers refuse them.
NOT_A_GUID = [str(GUID), GUID.bytes, GUID.int]
NOT_AN_INTEGER = [True, 7.0, "7"]


def _identifier_fields():
    """(model, payload fixture, field, is GUID) for every identifier field (named *_id) of every response model."""
    for model, payload_fixture in RESPONSE_MODELS:
        for name, field in model.model_fields.items():
            if name.endswith("_id"):
                yield pytest.param(model, payload_fixture, name, "UUID" in str(field.annotation),
                                   id=f"{model.__name__}.{name}")


@pytest.mark.parametrize("model, payload_fixture, field, is_guid", list(_identifier_fields()))
def test_identifier_accepts_only_the_type_of_its_key(request, model, payload_fixture, field, is_guid,
                                                     assert_rejected):
    payload = request.getfixturevalue(payload_fixture)
    valid, invalid = (GUID, NOT_A_GUID) if is_guid else (7, NOT_AN_INTEGER)

    assert getattr(model(**{**payload, field: valid}), field) == valid
    for value in invalid:
        assert_rejected(model, {**payload, field: value}, field)


@pytest.mark.parametrize("identifier_type, valid, invalid", [(GuidId, GUID, NOT_A_GUID), (IntegerId, 7, NOT_AN_INTEGER)],
                         ids=["GuidId", "IntegerId"])
def test_identifier_types(identifier_type, valid, invalid):
    adapter = TypeAdapter(identifier_type)

    assert adapter.validate_python(valid) == valid
    for value in invalid:
        with pytest.raises(ValidationError):
            adapter.validate_python(value)


def test_guid_identifier_is_read_from_json_text():
    assert TypeAdapter(GuidId).validate_json(f'"{GUID}"') == GUID


def test_integer_identifier_is_read_from_a_json_number_only():
    assert TypeAdapter(IntegerId).validate_json("7") == 7
    with pytest.raises(ValidationError):
        TypeAdapter(IntegerId).validate_json('"7"')


@pytest.mark.parametrize("model, field", MONEY_FIELDS, ids=[f"{model.__name__}.{field}" for model, field in MONEY_FIELDS])
def test_money_fields_accept_floats_exactly(request, model, field):
    payload = request.getfixturevalue(dict(RESPONSE_MODELS)[model])
    value = getattr(model(**{**payload, field: 1234567.05}), field)

    assert isinstance(value, Decimal)
    assert value == Decimal("1234567.05")  # not 1234567.0500000000465...


def test_money_type_is_a_decimal_annotation():
    assert Decimal in _types_in(Money)
