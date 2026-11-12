"""Shared configuration from Models/Dtos/Request/base_request.py, verified through the request models that use it."""
import importlib
import inspect
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from Models.Dtos.Request.AccountTypeRequest import AccountTypeRequest
from Models.Dtos.Request.CustomerRequest import CustomerRequest
from Models.Dtos.Request.CustomerUpdateRequest import CustomerUpdateRequest
from Models.Dtos.Request.RoleRequest import RoleRequest
from Models.Dtos.Request.StaffCreateRequest import StaffCreateRequest
from Models.Dtos.Request.StaffUpdateRequest import StaffUpdateRequest
from Models.Dtos.Request.UpdateUserRequest import UpdateUserRequest
from Models.Dtos.Request.UserRequest import UserRequest
from Models.Dtos.Request.base_request import BaseRequest
from Models.Dtos.Request.fund_account_request import FundAccountRequest
from Models.Dtos.Request.pagination_request import PaginationRequest
from Models.Dtos.Request.transaction_request import (
    FundsTransferRequest,
    TransactionRequest,
    TransactionsRequest,
    UserTransactionsRequest,
)

# Every request model with the fixture that provides a valid payload (None: all fields have defaults).
REQUEST_MODELS = [
    (AccountTypeRequest, "account_type_payload"),
    (CustomerRequest, "customer_payload"),
    (CustomerUpdateRequest, "customer_update_payload"),
    (RoleRequest, "role_payload"),
    (StaffCreateRequest, "staff_create_payload"),
    (StaffUpdateRequest, "staff_update_payload"),
    (UpdateUserRequest, "update_user_payload"),
    (UserRequest, "user_payload"),
    (FundAccountRequest, "fund_account_payload"),
    (PaginationRequest, None),
    (TransactionRequest, "transaction_payload"),
    (UserTransactionsRequest, "user_transactions_payload"),
    (TransactionsRequest, None),
    (FundsTransferRequest, "funds_transfer_payload"),
]
REQUEST_MODEL_IDS = [model.__name__ for model, _ in REQUEST_MODELS]
REQUEST_PACKAGE_DIR = Path(inspect.getfile(BaseRequest)).parent
REQUEST_PACKAGE = BaseRequest.__module__.rsplit(".", 1)[0]  # e.g. "Models.Dtos.Request"


@pytest.fixture(params=REQUEST_MODELS, ids=REQUEST_MODEL_IDS)
def model_and_payload(request):
    model, payload_fixture = request.param
    payload = request.getfixturevalue(payload_fixture) if payload_fixture else {}
    return model, payload


def _discover_request_models():
    models = set()
    for path in REQUEST_PACKAGE_DIR.glob("*.py"):
        if path.stem == "__init__":
            continue
        module = importlib.import_module(f"{REQUEST_PACKAGE}.{path.stem}")
        for _, member in inspect.getmembers(module, inspect.isclass):
            if issubclass(member, BaseModel) and member.__module__ == module.__name__ and member is not BaseRequest:
                models.add(member)
    return models


def test_every_request_model_uses_the_shared_base_and_is_covered_here():
    discovered = _discover_request_models()

    assert all(issubclass(model, BaseRequest) for model in discovered)
    assert discovered == {model for model, _ in REQUEST_MODELS}


def test_valid_payload_is_accepted(model_and_payload):
    model, payload = model_and_payload

    assert isinstance(model(**payload), model)


def test_unknown_field_is_rejected(model_and_payload, assert_rejected):
    model, payload = model_and_payload

    assert_rejected(model, {**payload, "unexpected_field": "value"}, "unexpected_field", "extra_forbidden")


def test_request_cannot_be_modified_after_construction(model_and_payload):
    model, payload = model_and_payload
    request = model(**payload)
    field = next(iter(model.model_fields))

    with pytest.raises(ValidationError) as exc_info:
        setattr(request, field, getattr(request, field))

    assert exc_info.value.errors()[0]["type"] == "frozen_instance"


def test_positional_arguments_are_rejected(user_payload):
    with pytest.raises(TypeError):
        UserRequest(*user_payload.values())


def test_validation_error_is_a_value_error(user_payload):
    # main.py reports invalid requests through its `except ValueError` handler.
    with pytest.raises(ValueError):
        UserRequest(**{**user_payload, "email": "invalid"})


@pytest.mark.parametrize("model, payload_fixture, field, submitted_value", [
    (UserRequest, "user_payload", "password", "Zq9#x"),
    (CustomerRequest, "customer_payload", "password", "Zq9#x"),
    (StaffCreateRequest, "staff_create_payload", "password", "Zq9#x" * 20),
    (CustomerUpdateRequest, "customer_update_payload", "password", "Zq9#xSecret"),
    (StaffUpdateRequest, "staff_update_payload", "password", "Zq9#xSecret"),
    (UpdateUserRequest, "update_user_payload", "email", "zq9x-private-address"),
    (FundsTransferRequest, "funds_transfer_payload", "sender_account_number", "Zq9x1234"),
], ids=["user-password", "customer-password", "staff-password", "customer-update-password",
        "staff-update-password", "email", "account-number"])
def test_submitted_values_are_not_echoed_in_error_messages(request, model, payload_fixture, field, submitted_value):
    payload = {**request.getfixturevalue(payload_fixture), field: submitted_value}

    with pytest.raises(ValidationError) as exc_info:
        model(**payload)

    assert field in str(exc_info.value)
    assert submitted_value not in str(exc_info.value)
