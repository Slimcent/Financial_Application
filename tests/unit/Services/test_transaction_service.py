"""TransactionService (Services/Implementations/transaction_service.py), run through a unit of work on the SQLite
test database.

The `bank` rows (tests/unit/Data/conftest.py):

    account      owner  type     balance   transactions
    2600000001   Ada    Savings  100.00    opening deposit 100.00
    2600000002   Ada    Current   50.00
    2600000003   Ben    Savings  200.00    opening deposit 200.00
    2600000004   Cy     Savings    0.00
    2600000005   Dee    Current   75.00    (Dee is staff; Ada, Ben and Cy are customers)

SQLite ignores row locks (FOR UPDATE): that the service asks for them is checked on the repository calls.
"""
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from Models.Constants.AppConstants import AppConstants
from Models.Dtos.Request.fund_account_request import FundAccountRequest
from Models.Dtos.Request.transaction_request import FundsTransferRequest, TransactionsRequest, UserTransactionsRequest
from Models.Dtos.Response.AccountResponse import AccountResponse
from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Response.paged_response import PagedResponse
from Models.Dtos.Response.transaction_response import TransactionResponse, TransactionsResponse
from Models.Entities import Account, Transaction
from Services.Exceptions.domain_exceptions import (BusinessRuleError, InsufficientFundsError, NotFoundError,
                                                   PersistenceError, ServiceError)
from Services.Implementations.transaction_service import RECENT_TRANSACTIONS_LIMIT, TransactionService
from Services.Interfaces.i_transaction_service import ITransactionService
from tests.unit.Services.conftest import SERVICE_TEST_MARKS, assert_no_personal_data
from tests.unit.Services.service_contract import assert_implements, assert_takes_the_unit_of_work_first, operations

pytestmark = SERVICE_TEST_MARKS

MISSING_USER_ID = uuid.UUID(int=404)
OPENING_BALANCES = {"2600000001": Decimal("100.00"), "2600000002": Decimal("50.00"), "2600000003": Decimal("200.00"),
                    "2600000004": Decimal("0.00"), "2600000005": Decimal("75.00")}


async def _transactions(persisted, *criteria):
    return await persisted.all(select(Transaction).where(*criteria))


@pytest.fixture
def fund_request(customer_ids):
    """A valid FundAccountRequest for one of the owner's accounts."""

    async def _fund_request(owner="Ada", account_number="2600000001", amount="25.50", description="Cash deposit",
                            transaction_type_id=AppConstants.DepositTransactionTypeId,
                            transaction_mode_id=AppConstants.CreditTransactionModeId):
        return FundAccountRequest(customer_id=(await customer_ids())[owner], account_number=account_number,
                                  amount=amount, transaction_type_id=transaction_type_id,
                                  transaction_mode_id=transaction_mode_id, description=description)

    return _fund_request


def _transfer_request(amount="30.25", sender="2600000001", receiver="2600000003", description="Rent"):
    return FundsTransferRequest(amount=amount, sender_account_number=sender, receiver_account_number=receiver,
                                description=description)


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------

def test_implements_its_interface():
    assert_implements(TransactionService, ITransactionService)


@pytest.mark.parametrize("name", operations(ITransactionService))
def test_every_operation_takes_the_callers_unit_of_work(name):
    assert_takes_the_unit_of_work_first(TransactionService, ITransactionService, name)


# ---------------------------------------------------------------------------
# fund_account
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestFundAccount:
    async def test_credits_the_account_and_records_a_completed_deposit(self, transaction_service, unit_of_work,
                                                                       persisted, bank, fund_request, balances,
                                                                       save_spy):
        response = await transaction_service.fund_account(unit_of_work, await fund_request())

        assert (await balances())["2600000001"] == Decimal("125.50")
        [recorded] = await _transactions(persisted, Transaction.Description == "Cash deposit")
        assert (recorded.AccountId, recorded.UserId, recorded.SenderId, recorded.Amount) == \
            (bank.account_id("2600000001"), bank.user_ids["Ada"], bank.user_ids["Ada"], Decimal("25.50"))
        assert (recorded.TransactionTypeId, recorded.TransactionModeId, recorded.TransactionStatusId,
                recorded.TransferReference) == (AppConstants.DepositTransactionTypeId,
                                                AppConstants.CreditTransactionModeId,
                                                AppConstants.CompletedTransactionStatusId, None)
        assert isinstance(response, AccountsResponse)
        assert (response.account_number, response.balance, response.account_type) == ("2600000001",
                                                                                       Decimal("125.50"), "Savings")
        assert response.active is True
        save_spy.assert_awaited_once()  # balance and transaction row in one transaction

    async def test_account_row_is_locked_while_its_balance_changes(self, transaction_service, unit_of_work,
                                                                   fund_request, monkeypatch):
        spy = AsyncMock(wraps=unit_of_work.accounts.get_single_async)
        monkeypatch.setattr(unit_of_work.accounts, "get_single_async", spy)

        await transaction_service.fund_account(unit_of_work, await fund_request())

        assert spy.await_args.kwargs["for_update"] is True

    @pytest.mark.parametrize("type_id, mode_id", [
        (AppConstants.TransferTransactionTypeId, AppConstants.CreditTransactionModeId),
        (AppConstants.WithdrawalTransactionTypeId, AppConstants.CreditTransactionModeId),
        (AppConstants.DepositTransactionTypeId, AppConstants.DebitTransactionModeId),
    ], ids=["transfer-type", "withdrawal-type", "debit-mode"])
    async def test_only_a_deposit_credit_funds_an_account(self, transaction_service, unit_of_work, persisted,
                                                          fund_request, balances, type_id, mode_id, save_spy):
        request = await fund_request(transaction_type_id=type_id, transaction_mode_id=mode_id)

        with pytest.raises(BusinessRuleError):
            await transaction_service.fund_account(unit_of_work, request)

        assert await balances() == OPENING_BALANCES
        assert await persisted.count(Transaction) == 2
        save_spy.assert_not_awaited()

    @pytest.mark.parametrize("owner, account_number", [("Ben", "2600000001"), ("Ada", "2699999999")],
                             ids=["account-of-another-customer", "missing-account"])
    async def test_account_must_belong_to_the_customer(self, transaction_service, unit_of_work, fund_request,
                                                       balances, owner, account_number):
        with pytest.raises(NotFoundError, match="has no account with this account number"):
            await transaction_service.fund_account(unit_of_work, await fund_request(owner=owner,
                                                                                    account_number=account_number))

        assert await balances() == OPENING_BALANCES

    async def test_missing_customer_is_not_found(self, transaction_service, unit_of_work, fund_request):
        request = (await fund_request()).model_copy(update={"customer_id": MISSING_USER_ID})

        with pytest.raises(NotFoundError):
            await transaction_service.fund_account(unit_of_work, request)

    async def test_inactive_customer_cannot_be_funded(self, transaction_service, user_service, unit_of_work, bank,
                                                      fund_request, balances):
        await user_service.toggle_user_active_status(unit_of_work, bank.user_ids["Ada"])

        with pytest.raises(BusinessRuleError, match="not active"):
            await transaction_service.fund_account(unit_of_work, await fund_request())

        assert await balances() == OPENING_BALANCES

    async def test_inactive_account_of_an_active_customer_cannot_be_funded(self, transaction_service, unit_of_work,
                                                                           persisted, fund_request, balances,
                                                                           deactivate_account, save_spy):
        await deactivate_account("2600000001")

        with pytest.raises(BusinessRuleError, match="The account is not active"):
            await transaction_service.fund_account(unit_of_work, await fund_request())

        assert await balances() == OPENING_BALANCES
        assert await persisted.count(Transaction) == 2
        save_spy.assert_not_awaited()

    async def test_other_active_account_of_the_customer_can_still_be_funded(self, transaction_service, unit_of_work,
                                                                            fund_request, balances,
                                                                            deactivate_account):
        await deactivate_account("2600000001")

        await transaction_service.fund_account(unit_of_work, await fund_request(account_number="2600000002"))

        assert (await balances())["2600000002"] == Decimal("75.50")

    async def test_deactivated_customer_account_cannot_be_funded(self, transaction_service, customer_service,
                                                                 unit_of_work, bank, fund_request, balances):
        await customer_service.deactivate_customer_account(unit_of_work, bank.user_ids["Ada"])

        with pytest.raises(BusinessRuleError):
            await transaction_service.fund_account(unit_of_work, await fund_request())

        assert await balances() == OPENING_BALANCES

    async def test_failed_save_changes_no_balance(self, transaction_service, unit_of_work, persisted, fund_request,
                                                  balances, failing_trigger):
        await failing_trigger("BEFORE INSERT ON Transactions")

        with pytest.raises(PersistenceError, match="could not be funded"):
            await transaction_service.fund_account(unit_of_work, await fund_request())

        assert await balances() == OPENING_BALANCES
        assert await persisted.count(Transaction) == 2

    async def test_repeated_funding_adds_up_exactly(self, transaction_service, unit_of_work, fund_request, balances):
        for amount in ("0.10", "0.20", "0.30"):
            await transaction_service.fund_account(unit_of_work, await fund_request(account_number="2600000002",
                                                                                    amount=amount))

        assert (await balances())["2600000002"] == Decimal("50.60")


# ---------------------------------------------------------------------------
# transfer_funds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestTransferFunds:
    async def test_moves_the_amount_and_records_the_debit_and_the_credit(self, transaction_service, unit_of_work,
                                                                         persisted, bank, balances, save_spy):
        response = await transaction_service.transfer_funds(unit_of_work, _transfer_request())

        assert {number: balance for number, balance in (await balances()).items()
                if number in ("2600000001", "2600000003")} == {"2600000001": Decimal("69.75"),
                                                               "2600000003": Decimal("230.25")}
        rows = await _transactions(persisted, Transaction.Description == "Rent")
        by_mode = {row.TransactionModeId: row for row in rows}
        debit = by_mode[AppConstants.DebitTransactionModeId]
        credit = by_mode[AppConstants.CreditTransactionModeId]
        assert (debit.AccountId, debit.UserId) == (bank.account_id("2600000001"), bank.user_ids["Ada"])
        assert (credit.AccountId, credit.UserId) == (bank.account_id("2600000003"), bank.user_ids["Ben"])
        for row in (debit, credit):
            assert (row.Amount, row.SenderId, row.TransactionTypeId, row.TransactionStatusId) == \
                (Decimal("30.25"), bank.user_ids["Ada"], AppConstants.TransferTransactionTypeId,
                 AppConstants.CompletedTransactionStatusId)
        assert (response.account_number, response.balance) == ("2600000001", Decimal("69.75"))
        save_spy.assert_awaited_once()  # both balances and both rows in one transaction

    async def test_debit_and_credit_share_one_transfer_reference(self, transaction_service, unit_of_work, persisted):
        await transaction_service.transfer_funds(unit_of_work, _transfer_request(description="First"))
        await transaction_service.transfer_funds(unit_of_work, _transfer_request(description="Second"))

        first = {row.TransferReference for row in await _transactions(persisted, Transaction.Description == "First")}
        second = {row.TransferReference for row in await _transactions(persisted, Transaction.Description == "Second")}
        assert len(first) == 1 and len(second) == 1
        assert None not in first and first != second

    async def test_both_rows_are_locked_by_one_query_in_primary_key_order(self, transaction_service, unit_of_work,
                                                                          monkeypatch):
        spy = AsyncMock(wraps=unit_of_work.accounts.get_range_async)
        monkeypatch.setattr(unit_of_work.accounts, "get_range_async", spy)

        await transaction_service.transfer_funds(unit_of_work, _transfer_request())

        spy.assert_awaited_once()
        assert spy.await_args.kwargs["for_update"] is True
        assert [str(term) for term in spy.await_args.kwargs["order_by"]] == [str(Account.Id)]

    async def test_the_whole_balance_can_be_transferred(self, transaction_service, unit_of_work, balances):
        await transaction_service.transfer_funds(unit_of_work, _transfer_request(amount="100.00"))

        assert (await balances())["2600000001"] == Decimal("0.00")

    async def test_insufficient_funds_change_nothing(self, transaction_service, unit_of_work, persisted, balances,
                                                     save_spy):
        with pytest.raises(InsufficientFundsError, match="insufficient funds"):
            await transaction_service.transfer_funds(unit_of_work, _transfer_request(amount="100.01"))

        assert await balances() == OPENING_BALANCES
        assert await persisted.count(Transaction) == 2
        save_spy.assert_not_awaited()

    @pytest.mark.parametrize("sender, receiver, missing", [("2699999999", "2600000003", "Sender"),
                                                           ("2600000001", "2699999999", "Receiver")],
                             ids=["missing-sender", "missing-receiver"])
    async def test_missing_account_is_not_found(self, transaction_service, unit_of_work, balances, sender, receiver,
                                                missing):
        with pytest.raises(NotFoundError, match=f"The {missing.lower()} account does not exist"):
            await transaction_service.transfer_funds(unit_of_work, _transfer_request(sender=sender,
                                                                                     receiver=receiver))

        assert await balances() == OPENING_BALANCES

    @pytest.mark.parametrize("inactive, side", [("Ada", "sender"), ("Ben", "receiver")])
    async def test_inactive_user_on_either_side_is_refused(self, transaction_service, user_service, unit_of_work,
                                                           bank, balances, inactive, side):
        await user_service.toggle_user_active_status(unit_of_work, bank.user_ids[inactive])

        with pytest.raises(BusinessRuleError, match=f"{side} account"):
            await transaction_service.transfer_funds(unit_of_work, _transfer_request())

        assert await balances() == OPENING_BALANCES

    @pytest.mark.parametrize("account_number, side", [("2600000001", "sender"), ("2600000003", "receiver")])
    async def test_inactive_account_on_either_side_is_refused(self, transaction_service, unit_of_work, persisted,
                                                              balances, deactivate_account, account_number, side,
                                                              save_spy):
        await deactivate_account(account_number)  # the owner stays active

        with pytest.raises(BusinessRuleError, match=f"The {side} account is not active"):
            await transaction_service.transfer_funds(unit_of_work, _transfer_request())

        assert await balances() == OPENING_BALANCES
        assert await persisted.count(Transaction) == 2
        save_spy.assert_not_awaited()

    async def test_deactivated_customer_cannot_receive(self, transaction_service, customer_service, unit_of_work,
                                                       bank, balances):
        await customer_service.deactivate_customer_account(unit_of_work, bank.user_ids["Ben"])

        with pytest.raises(BusinessRuleError):
            await transaction_service.transfer_funds(unit_of_work, _transfer_request())

        assert await balances() == OPENING_BALANCES

    async def test_failed_save_changes_no_balance(self, transaction_service, unit_of_work, persisted, balances,
                                                  failing_trigger):
        await failing_trigger("BEFORE INSERT ON Transactions")

        with pytest.raises(PersistenceError, match="transfer could not be completed"):
            await transaction_service.transfer_funds(unit_of_work, _transfer_request())

        assert await balances() == OPENING_BALANCES
        assert await persisted.count(Transaction) == 2


def test_insufficient_funds_is_a_business_rule():
    assert issubclass(InsufficientFundsError, BusinessRuleError)


# ---------------------------------------------------------------------------
# get_user_transactions / filter_user_transactions
# ---------------------------------------------------------------------------

@pytest.fixture
def history(transaction_service, unit_of_work, fund_request):
    """Ada's accounts get a deposit into the current account and send a transfer to Ben; Ben then sends one back."""

    async def _history():
        await transaction_service.fund_account(unit_of_work, await fund_request(account_number="2600000002",
                                                                                amount="5.00",
                                                                                description="Top-up"))
        await transaction_service.transfer_funds(unit_of_work, _transfer_request(amount="10.00", description="Rent"))
        await transaction_service.transfer_funds(unit_of_work, _transfer_request(
            amount="1.00", sender="2600000003", receiver="2600000001", description="Refund"))

    return _history


@pytest.mark.asyncio
class TestUserTransactions:
    async def test_transactions_of_the_users_accounts_newest_first(self, transaction_service, unit_of_work, bank,
                                                                   history, save_spy):
        await history()
        save_spy.reset_mock()

        response = await transaction_service.get_user_transactions(unit_of_work, bank.user_ids["Ada"])

        assert isinstance(response, AccountResponse)
        assert all(isinstance(item, TransactionResponse) for item in response.transactions)
        assert [(item.description, item.transaction_mode, item.amount) for item in response.transactions] == [
            ("Refund", "Credit", Decimal("1.00")), ("Rent", "Debit", Decimal("10.00")),
            ("Top-up", "Credit", Decimal("5.00")), ("opening deposit", "Credit", Decimal("100.00"))]
        assert response.transactions[0].sender == "Ben Okafor"
        save_spy.assert_not_awaited()

    async def test_total_balance_is_the_sum_of_the_account_balances(self, transaction_service, unit_of_work, bank,
                                                                    history):
        await history()

        response = await transaction_service.get_user_transactions(unit_of_work, bank.user_ids["Ada"])

        # 100 - 10 + 1 (savings) + 50 + 5 (current)
        assert response.total_balance == Decimal("146.00")
        assert isinstance(response.total_balance, Decimal)

    async def test_owner_details_are_included(self, transaction_service, unit_of_work, bank):
        response = await transaction_service.get_user_transactions(unit_of_work, bank.user_ids["Ada"])

        assert (response.user_id, response.first_name, response.address) == (bank.user_ids["Ada"], "Ada",
                                                                             "Ada Street")
        assert response.customer_id is not None
        assert response.active is True

    async def test_inactive_owner_is_shown_as_inactive(self, transaction_service, user_service, unit_of_work, bank):
        await user_service.toggle_user_active_status(unit_of_work, bank.user_ids["Ada"])

        response = await transaction_service.get_user_transactions(unit_of_work, bank.user_ids["Ada"])

        assert response.active is False

    async def test_staff_member_has_no_customer_details(self, transaction_service, unit_of_work, bank):
        response = await transaction_service.get_user_transactions(unit_of_work, bank.user_ids["Dee"])

        assert (response.customer_id, response.address, response.transactions, response.total_balance) == \
            (None, None, [], Decimal("75.00"))

    async def test_missing_user_is_not_found(self, transaction_service, unit_of_work):
        with pytest.raises(NotFoundError):
            await transaction_service.get_user_transactions(unit_of_work, MISSING_USER_ID)

    @pytest.mark.parametrize("filters, expected", [
        pytest.param({}, ["Refund", "Rent", "Top-up", "opening deposit"], id="no-filter"),
        pytest.param({"transaction_type_id": AppConstants.TransferTransactionTypeId}, ["Refund", "Rent"],
                     id="transaction-type"),
        pytest.param({"transaction_mode_id": AppConstants.DebitTransactionModeId}, ["Rent"], id="transaction-mode"),
        pytest.param({"account_number": "2600000002"}, ["Top-up"], id="account-number"),
        pytest.param({"account_type_id": AppConstants.SavingsAccountTypeId}, ["Refund", "Rent", "opening deposit"],
                     id="account-type"),
        pytest.param({"transaction_status_id": AppConstants.PendingTransactionStatusId}, [], id="status"),
        pytest.param({"sender_id": "Ben"}, ["Refund"], id="sender"),
        pytest.param({"transaction_type_id": AppConstants.TransferTransactionTypeId,
                      "transaction_mode_id": AppConstants.CreditTransactionModeId}, ["Refund"], id="combined"),
    ])
    async def test_filters_are_applied_in_the_query(self, transaction_service, unit_of_work, bank, history,
                                                    filters, expected):
        await history()
        if "sender_id" in filters:
            filters = {**filters, "sender_id": bank.user_ids[filters["sender_id"]]}

        response = await transaction_service.filter_user_transactions(
            unit_of_work, UserTransactionsRequest(user_id=bank.user_ids["Ada"], **filters))

        assert [item.description for item in response.transactions] == expected

    async def test_filtering_does_not_change_the_user_or_its_transactions(self, transaction_service, unit_of_work,
                                                                          persisted, bank, history):
        await history()
        before = await persisted.count(Transaction, Transaction.UserId == bank.user_ids["Ada"])

        await transaction_service.filter_user_transactions(
            unit_of_work, UserTransactionsRequest(user_id=bank.user_ids["Ada"], account_number="2600000002"))
        await unit_of_work.save_changes_async()  # nothing was staged: saving writes nothing

        assert await persisted.count(Transaction, Transaction.UserId == bank.user_ids["Ada"]) == before


# ---------------------------------------------------------------------------
# get_all_transactions_paginated / get_all_transactions_non_paginated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAllTransactions:
    async def test_page_holds_its_items_and_the_total_count(self, transaction_service, unit_of_work, history):
        await history()  # 2 opening deposits + 1 deposit + 2 transfers of 2 rows = 7 transactions

        first = await transaction_service.get_all_transactions_paginated(unit_of_work,
                                                                         TransactionsRequest(page=1, page_size=3))
        last = await transaction_service.get_all_transactions_paginated(unit_of_work,
                                                                        TransactionsRequest(page=3, page_size=3))

        assert isinstance(first, PagedResponse)
        assert all(isinstance(item, TransactionsResponse) for item in first.items)
        assert (first.total_count, first.page, first.page_size, len(first.items)) == (7, 1, 3, 3)
        assert (last.total_count, len(last.items)) == (7, 1)
        assert [item.description for item in first.items[:2]] == ["Refund", "Refund"]

    async def test_pages_cover_every_transaction_once(self, transaction_service, unit_of_work, persisted, history):
        await history()

        seen = []
        for page in (1, 2, 3):
            response = await transaction_service.get_all_transactions_paginated(
                unit_of_work, TransactionsRequest(page=page, page_size=3))
            seen += [(item.account_id, item.description, item.transaction_mode) for item in response.items]

        assert len(seen) == len(set(seen)) == await persisted.count(Transaction)

    async def test_page_after_the_last_is_empty(self, transaction_service, unit_of_work):
        response = await transaction_service.get_all_transactions_paginated(unit_of_work,
                                                                            TransactionsRequest(page=5, page_size=10))

        assert (response.total_count, response.items) == (2, [])

    async def test_paging_is_done_by_the_database(self, transaction_service, unit_of_work, sql_statements):
        await transaction_service.get_all_transactions_paginated(unit_of_work, TransactionsRequest(page=2,
                                                                                                   page_size=1))

        transaction_queries = [statement for statement in sql_statements if "FROM Transactions" in statement]
        assert any(statement.startswith("SELECT count(*)") for statement in transaction_queries)
        assert any("LIMIT ? OFFSET ?" in statement for statement in transaction_queries)

    async def test_items_include_the_account_owner(self, transaction_service, unit_of_work, bank):
        response = await transaction_service.get_all_transactions_paginated(
            unit_of_work, TransactionsRequest(user_id=bank.user_ids["Ben"]))

        [item] = response.items
        assert (item.user_id, item.first_name, item.address, item.account_number, item.amount) == \
            (bank.user_ids["Ben"], "Ben", "Ben Street", "2600000003", Decimal("200.00"))
        assert item.customer_id is not None and item.staff_id is None

    @pytest.mark.parametrize("search_term, expected_owners", [
        pytest.param("ADA", {"Ada"}, id="first-name-any-case"),
        pytest.param("okafor", {"Ben"}, id="last-name"),
        pytest.param("example2@example.com", {"Ben"}, id="email"),
        pytest.param("2600000002", {"Ada"}, id="account-number"),
        pytest.param("26000000", {"Ada", "Ben"}, id="account-number-part"),
        pytest.param("nobody", set(), id="no-match"),
        pytest.param("%", set(), id="percent-is-literal"),
        pytest.param("_", set(), id="underscore-is-literal"),
    ])
    async def test_search_term(self, transaction_service, unit_of_work, bank, history, search_term,
                               expected_owners):
        await history()

        response = await transaction_service.get_all_transactions_paginated(
            unit_of_work, TransactionsRequest(search_term=search_term, page_size=50))

        owner_names = {name for name, user_id in bank.user_ids.items()}
        assert {name for name in owner_names
                if bank.user_ids[name] in {item.user_id for item in response.items}} == expected_owners
        assert response.total_count == len(response.items)

    @pytest.mark.parametrize("filters, expected_count", [
        pytest.param({"account_number": "2600000001"}, 3, id="account-number"),
        pytest.param({"transaction_type_id": AppConstants.DepositTransactionTypeId}, 3, id="transaction-type"),
        pytest.param({"transaction_mode_id": AppConstants.DebitTransactionModeId}, 2, id="transaction-mode"),
        pytest.param({"account_type_id": AppConstants.CurrentAccountTypeId}, 1, id="account-type"),
    ])
    async def test_filters_are_applied_to_the_page_and_the_total(self, transaction_service, unit_of_work, history,
                                                                 filters, expected_count):
        await history()

        response = await transaction_service.get_all_transactions_paginated(
            unit_of_work, TransactionsRequest(page_size=1, **filters))

        assert response.total_count == expected_count
        assert len(response.items) == 1

    async def test_non_paginated_returns_the_most_recent_transactions_up_to_the_cap(
            self, transaction_service, unit_of_work, fund_request, persisted):
        for number in range(RECENT_TRANSACTIONS_LIMIT + 2):
            await transaction_service.fund_account(unit_of_work, await fund_request(description=f"Deposit {number}",
                                                                                    amount="1.00"))
        assert await persisted.count(Transaction) == RECENT_TRANSACTIONS_LIMIT + 4

        response = await transaction_service.get_all_transactions_non_paginated(unit_of_work, TransactionsRequest())

        assert RECENT_TRANSACTIONS_LIMIT == 15
        assert [item.description for item in response] == \
            [f"Deposit {number}" for number in range(RECENT_TRANSACTIONS_LIMIT + 1, 1, -1)]

    async def test_non_paginated_ignores_the_page(self, transaction_service, unit_of_work, history):
        await history()

        response = await transaction_service.get_all_transactions_non_paginated(
            unit_of_work, TransactionsRequest(page=3, page_size=1))

        assert len(response) == 7
        assert all(isinstance(item, TransactionsResponse) for item in response)

    async def test_non_paginated_filters_before_capping(self, transaction_service, unit_of_work, bank, history):
        await history()

        response = await transaction_service.get_all_transactions_non_paginated(
            unit_of_work, TransactionsRequest(user_id=bank.user_ids["Ben"]))

        assert [item.description for item in response] == ["Refund", "Rent", "opening deposit"]

    async def test_non_paginated_limits_the_query(self, transaction_service, unit_of_work, sql_statements):
        await transaction_service.get_all_transactions_non_paginated(unit_of_work, TransactionsRequest())

        [query] = [statement for statement in sql_statements if "FROM Transactions" in statement]
        assert "LIMIT ?" in query and "ORDER BY Transactions.TransactionDate DESC, Transactions.Id DESC" in query


# ---------------------------------------------------------------------------
# Error messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_messages_do_not_contain_account_numbers_or_email_addresses(
        transaction_service, user_service, unit_of_work, bank, fund_request, deactivate_account):
    messages = []

    async def message_of(operation):
        with pytest.raises(ServiceError) as exc_info:
            await operation
        messages.append(exc_info.value.message)

    await message_of(transaction_service.fund_account(unit_of_work, await fund_request(owner="Ben")))
    await message_of(transaction_service.fund_account(unit_of_work, await fund_request(account_number="2699999999")))
    await message_of(transaction_service.transfer_funds(unit_of_work, _transfer_request(sender="2699999999")))
    await message_of(transaction_service.transfer_funds(unit_of_work, _transfer_request(receiver="2699999999")))
    await message_of(transaction_service.transfer_funds(unit_of_work, _transfer_request(amount="999.00")))
    await deactivate_account("2600000003")
    await message_of(transaction_service.transfer_funds(unit_of_work, _transfer_request()))
    await user_service.toggle_user_active_status(unit_of_work, bank.user_ids["Ada"])
    await message_of(transaction_service.fund_account(unit_of_work, await fund_request()))
    await message_of(transaction_service.transfer_funds(unit_of_work, _transfer_request()))

    assert len(messages) == 8
    for message in messages:
        assert_no_personal_data(message)
