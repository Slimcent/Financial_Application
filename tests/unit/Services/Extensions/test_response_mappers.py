"""Services/Extensions/response_mappers.py: the include lists load what the mappers read, and the totals and
ordering the responses show. (Field by field mapping is covered by the response tests in
tests/unit/Models/Dtos/Response.)"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy.exc import InvalidRequestError

from Models.Entities import Account
from Services.Extensions.response_mappers import (TRANSACTION_INCLUDES, TRANSACTIONS_INCLUDES, ZERO,
                                                  to_accounts_responses, to_transaction_response,
                                                  to_transactions_response, total_balance)
from tests.unit.Services.conftest import SERVICE_TEST_MARKS

pytestmark = SERVICE_TEST_MARKS


def test_total_balance_of_no_accounts_is_a_two_place_zero():
    total = total_balance([])

    assert total == ZERO == Decimal("0.00")
    assert total.as_tuple().exponent == -2


def test_total_balance_adds_the_balances_exactly():
    accounts = [Account(Balance=Decimal("0.10")), Account(Balance=Decimal("0.20")), Account(Balance=Decimal("0.30"))]

    assert total_balance(accounts) == Decimal("0.60")


def test_accounts_are_listed_by_account_type():
    accounts = [Account(Id=uuid.uuid4(), AccountNumber="2", AccountTypeId=3, Balance=Decimal("1"), Active=True),
                Account(Id=uuid.uuid4(), AccountNumber="1", AccountTypeId=1, Balance=Decimal("1"), Active=False),
                Account(Id=uuid.uuid4(), AccountNumber="3", AccountTypeId=2, Balance=Decimal("1"), Active=True)]

    assert [(response.account_number, response.active) for response in to_accounts_responses(accounts)] == \
        [("1", False), ("3", True), ("2", True)]


def test_transactions_includes_extend_the_transaction_includes():
    assert set(TRANSACTION_INCLUDES) < set(TRANSACTIONS_INCLUDES)


@pytest.mark.asyncio
@pytest.mark.parametrize("includes, mapper", [(TRANSACTION_INCLUDES, to_transaction_response),
                                              (TRANSACTIONS_INCLUDES, to_transactions_response)],
                         ids=["transaction", "transactions"])
async def test_includes_load_everything_the_mapper_reads(unit_of_work, includes, mapper):
    # Relationships never load implicitly: a missing include would make the mapper raise.
    transactions = await unit_of_work.transactions.get_range_async(includes=includes)

    responses = [mapper(transaction) for transaction in transactions]

    assert [response.amount for response in responses] == [Decimal("100.00"), Decimal("200.00")]


@pytest.mark.asyncio
async def test_mapping_without_the_includes_fails_instead_of_loading_lazily(unit_of_work):
    [transaction, _] = await unit_of_work.transactions.get_range_async()

    with pytest.raises(InvalidRequestError):
        to_transaction_response(transaction)
