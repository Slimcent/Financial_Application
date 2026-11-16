"""AccountResponse (Models/Dtos/Response/AccountResponse.py): a user with accounts and / or transactions."""
from decimal import Decimal

import pytest
from pydantic import ValidationError

from Models.Dtos.Response.AccountResponse import AccountResponse
from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Response.transaction_response import TransactionResponse
from Services.Extensions.response_mappers import to_account_response, to_transaction_response

FIELDS_WITHOUT_DEFAULT_VALUE = ["user_id", "customer_id", "last_name", "first_name", "address", "email", "active",
                                "balance", "total_balance"]
LIST_FIELDS = ["accounts", "transactions"]
MONEY_FIELDS = ["balance", "total_balance"]
TEXT_FIELDS = ["last_name", "first_name", "address", "email"]


def test_valid_response_is_accepted(account_response_payload):
    response = AccountResponse(**account_response_payload)

    assert response.model_dump() == account_response_payload


def test_every_field_is_optional():
    response = AccountResponse()

    assert all(getattr(response, field) is None for field in FIELDS_WITHOUT_DEFAULT_VALUE)
    assert (response.accounts, response.transactions) == ([], [])


@pytest.mark.parametrize("field", LIST_FIELDS)
def test_list_default_is_not_shared_between_responses(field):
    first, second = AccountResponse(), AccountResponse()
    getattr(first, field).append("changed")

    assert getattr(second, field) == []


def test_nested_items_are_validated_as_their_responses(account_response_payload):
    response = AccountResponse(**account_response_payload)

    assert isinstance(response.accounts[0], AccountsResponse)
    assert isinstance(response.transactions[0], TransactionResponse)


@pytest.mark.parametrize("field, item_field, value", [
    ("accounts", "balance", "abc"),
    ("transactions", "amount", "abc"),
    ("transactions", "transaction_date", "yesterday"),
])
def test_invalid_nested_item_is_reported_at_its_position(account_response_payload, field, item_field, value):
    items = [*account_response_payload[field], {**account_response_payload[field][0], item_field: value}]

    with pytest.raises(ValidationError) as exc_info:
        AccountResponse(**{**account_response_payload, field: items})

    assert [error["loc"] for error in exc_info.value.errors()] == [(field, 1, item_field)]


@pytest.mark.parametrize("field", MONEY_FIELDS)
def test_money_is_kept_as_an_exact_decimal(account_response_payload, field, valid_money):
    raw, expected = valid_money
    value = getattr(AccountResponse(**{**account_response_payload, field: raw}), field)

    assert isinstance(value, Decimal)
    assert value.as_tuple() == expected.as_tuple()


@pytest.mark.parametrize("field", MONEY_FIELDS)
def test_invalid_money_is_rejected(account_response_payload, field, invalid_optional_money, assert_rejected):
    assert_rejected(AccountResponse, {**account_response_payload, field: invalid_optional_money}, field)


@pytest.mark.parametrize("field", ["user_id", "customer_id"])
def test_invalid_identifier_is_rejected(account_response_payload, field, invalid_optional_guid, assert_rejected):
    assert_rejected(AccountResponse, {**account_response_payload, field: invalid_optional_guid}, field)


@pytest.mark.parametrize("field", TEXT_FIELDS)
def test_text_field_must_be_text(account_response_payload, field, invalid_text, assert_rejected):
    assert_rejected(AccountResponse, {**account_response_payload, field: invalid_text}, field)


@pytest.mark.parametrize("value", ["maybe", 2])
def test_invalid_active_flag_is_rejected(account_response_payload, value, assert_rejected):
    assert_rejected(AccountResponse, {**account_response_payload, "active": value}, "active")


def test_holder_and_accounts_have_their_own_active_flags(account_response_payload, accounts_response_payload):
    # An account holder can be active while one of the accounts is not (and the other way round).
    response = AccountResponse(**{**account_response_payload, "active": True,
                                  "accounts": [{**accounts_response_payload, "active": False}]})

    assert (response.active, response.accounts[0].active) == (True, False)


def test_serialised_as_json_values(account_response_payload):
    serialised = AccountResponse(**account_response_payload).model_dump(mode="json")

    assert (serialised["balance"], serialised["total_balance"]) == ("100.00", "150.00")
    assert serialised["accounts"][0]["balance"] == "100.00"
    assert serialised["transactions"][0]["amount"] == "25.50"
    assert serialised["transactions"][0]["transaction_date"] == "2026-11-15T10:45:12.123456Z"


# ---------------------------------------------------------------------------
# Compatibility with the services (Services/Extensions/response_mappers.py, TransactionService)
# ---------------------------------------------------------------------------

def test_user_accounts_map_to_a_valid_response(entity_graph):
    ada = entity_graph.ada

    response = to_account_response(ada, ada.accounts, customer=entity_graph.customer)

    assert isinstance(response, AccountResponse)
    assert (response.user_id, response.customer_id, response.address) == (ada.Id, entity_graph.customer.Id,
                                                                           "1 Main Street")
    assert response.active is True
    assert [account.active for account in response.accounts] == [True, True]
    assert [account.account_type for account in response.accounts] == ["Savings", "Current"]
    assert response.total_balance == Decimal("150.00")
    assert isinstance(response.total_balance, Decimal)
    assert response.balance is None
    assert response.transactions == []


def test_single_account_response_carries_its_balance(entity_graph):
    account = entity_graph.current_account

    response = to_account_response(entity_graph.ada, [account], customer=entity_graph.customer,
                                   balance=account.Balance)

    assert (response.balance, response.total_balance) == (Decimal("50.00"), Decimal("50.00"))


def test_deactivated_holder_and_account_map_to_inactive_flags(entity_graph):
    ada = entity_graph.ada
    ada.Active = False
    entity_graph.current_account.Active = False

    response = to_account_response(ada, ada.accounts, customer=entity_graph.customer)

    assert response.active is False
    assert [(account.account_number, account.active) for account in response.accounts] == \
        [("2600000001", True), ("2600000002", False)]


def test_user_without_accounts_has_a_zero_total_balance(entity_graph):
    response = to_account_response(entity_graph.ben, [])

    assert (response.accounts, response.total_balance, response.customer_id) == ([], Decimal("0.00"), None)


def test_transaction_history_response_is_valid(entity_graph):
    # As TransactionService builds it for a user's transactions.
    ada = entity_graph.ada
    response = AccountResponse(user_id=ada.Id, customer_id=entity_graph.customer.Id, last_name=ada.LastName,
                               first_name=ada.FirstName, address=entity_graph.customer.Address, email=ada.Email,
                               active=ada.Active, transactions=[to_transaction_response(entity_graph.transaction)],
                               total_balance=Decimal("150.00"))

    assert AccountResponse.model_validate_json(response.model_dump_json()) == response
    assert response.transactions[0].amount == Decimal("25.50")
