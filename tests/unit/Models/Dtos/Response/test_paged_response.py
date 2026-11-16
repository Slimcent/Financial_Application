"""PagedResponse (Models/Dtos/Response/paged_response.py): one page of items and the total count."""
import pytest
from pydantic import ValidationError

from Models.Dtos.Response.AccountTypeResponse import AccountTypeResponse
from Models.Dtos.Response.paged_response import PagedResponse
from Models.Dtos.Response.transaction_response import TransactionsResponse
from Models.Entities import Account
from Services.Extensions.response_mappers import to_transactions_response

REQUIRED_FIELDS = ["total_count", "page", "page_size", "items"]
COUNT_FIELDS = ["total_count", "page", "page_size"]


def test_valid_response_is_accepted(paged_response_payload):
    assert PagedResponse(**paged_response_payload).model_dump() == paged_response_payload


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_required_field_is_rejected(paged_response_payload, field, omit, assert_rejected):
    assert_rejected(PagedResponse, omit(paged_response_payload, field), field, "missing")


@pytest.mark.parametrize("value", ["abc", 1.5, "1.5", None], ids=["text", "fraction", "fraction-text", "none"])
@pytest.mark.parametrize("field", COUNT_FIELDS)
def test_invalid_count_is_rejected(paged_response_payload, field, value, assert_rejected):
    # Counts are not identifiers: like other numbers they are read from numeric text as well.
    assert_rejected(PagedResponse, {**paged_response_payload, field: value}, field)


def test_items_must_be_a_list(paged_response_payload, assert_rejected):
    assert_rejected(PagedResponse, {**paged_response_payload, "items": None}, "items", "list_type")


def test_empty_page_is_valid(paged_response_payload):
    response = PagedResponse(**{**paged_response_payload, "total_count": 0, "items": []})

    assert (response.total_count, response.items) == (0, [])


# ---------------------------------------------------------------------------
# Items: kept as they are without a type argument, validated with one
# ---------------------------------------------------------------------------

def test_items_without_a_type_argument_are_kept_as_given(paged_response_payload):
    # The repository pages entities: they must come back as the very same (tracked) objects.
    entities = [Account(AccountNumber="2600000001"), Account(AccountNumber="2600000002")]

    response = PagedResponse(**{**paged_response_payload, "items": entities})

    assert all(item is entity for item, entity in zip(response.items, entities, strict=True))


def test_type_argument_validates_and_converts_the_items(paged_response_payload):
    response = PagedResponse[AccountTypeResponse](**paged_response_payload)

    assert response.items == [AccountTypeResponse(account_type_id=1, name="Savings")]


def test_invalid_item_is_reported_at_its_position(paged_response_payload):
    items = [*paged_response_payload["items"], {"account_type_id": "abc", "name": "Current"}]

    with pytest.raises(ValidationError) as exc_info:
        PagedResponse[AccountTypeResponse](**{**paged_response_payload, "items": items})

    assert [error["loc"] for error in exc_info.value.errors()] == [("items", 1, "account_type_id")]


def test_entity_type_argument_checks_the_item_type(paged_response_payload):
    # Repository.get_range_async is typed PagedResponse[TEntity]; an entity type argument must be usable.
    account = Account(AccountNumber="2600000001")

    assert PagedResponse[Account](**{**paged_response_payload, "items": [account]}).items == [account]
    with pytest.raises(ValidationError) as exc_info:
        PagedResponse[Account](**{**paged_response_payload, "items": ["not an account"]})
    assert exc_info.value.errors()[0]["loc"] == ("items", 0)


def test_typed_page_serialises_its_items(paged_response_payload):
    serialised = PagedResponse[AccountTypeResponse](**paged_response_payload).model_dump(mode="json")

    assert serialised == {"total_count": 3, "page": 2, "page_size": 2,
                          "items": [{"account_type_id": 1, "name": "Savings"}]}


def test_typed_page_round_trips_through_json(paged_response_payload):
    model = PagedResponse[AccountTypeResponse]
    response = model(**paged_response_payload)

    assert model.model_validate_json(response.model_dump_json()) == response


# ---------------------------------------------------------------------------
# Compatibility with the services (TransactionService.get_all_transactions_paginated)
# ---------------------------------------------------------------------------

def test_page_of_transactions_as_the_service_builds_it(entity_graph):
    response = PagedResponse[TransactionsResponse](total_count=21, page=3, page_size=10,
                                                   items=[to_transactions_response(entity_graph.transaction)])

    serialised = response.model_dump(mode="json")

    assert (serialised["total_count"], serialised["page"], serialised["page_size"]) == (21, 3, 10)
    assert serialised["items"][0]["amount"] == "25.50"
    assert PagedResponse[TransactionsResponse].model_validate_json(response.model_dump_json()) == response
