"""CustomerService (Services/Implementations/CustomerService.py), run through a unit of work on the SQLite test
database.

The `bank` rows (tests/unit/Data/conftest.py):

    account      owner  type     balance   transactions
    2600000001   Ada    Savings  100.00    1
    2600000002   Ada    Current   50.00
    2600000003   Ben    Savings  200.00    1
    2600000004   Cy     Savings    0.00
    2600000005   Dee    Current   75.00    (Dee is staff; Ada, Ben and Cy are customers)
"""
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from Data.Implementations.unit_of_work import UnitOfWork
from Models.Constants.AppConstants import AppConstants
from Models.Dtos.Request.CustomerRequest import CustomerRequest
from Models.Dtos.Request.CustomerUpdateRequest import CustomerUpdateRequest
from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Response.UserResponse import UserResponse
from Models.Entities import Account, Customer, Role, Staff, User
from Services.Exceptions.domain_exceptions import (BusinessRuleError, ConflictError, DeleteRestrictedError,
                                                   InvalidInputError, NotFoundError, PersistenceError, ServiceError)
from Services.Implementations import CustomerService as customer_service_module
from Services.Implementations.CustomerService import (ACCOUNT_NUMBER_CONSTRAINT, CONFLICT_MESSAGES,
                                                      MAX_ACCOUNT_NUMBER_ATTEMPTS, MAX_SAVE_ATTEMPTS,
                                                      CustomerService)
from Services.Interfaces.i_customer_service import ICustomerService
from Services.Interfaces.i_user_service import IUserService
from tests.unit.Services.conftest import SERVICE_TEST_MARKS, assert_no_personal_data
from tests.unit.Services.service_contract import assert_implements, assert_takes_the_unit_of_work_first, operations

pytestmark = SERVICE_TEST_MARKS

MISSING_USER_ID = uuid.UUID(int=404)
TAKEN_ACCOUNT_NUMBER = "2600000001"
FREE_ACCOUNT_NUMBERS = ["2690000001", "2690000002"]


def _create_request(email="example5@example.com", account_type_id=AppConstants.SavingsAccountTypeId):
    return CustomerRequest(last_name="Hopper", first_name="Grace", email=email, address="3 Navy Road",
                           account_type_id=account_type_id, password="Str0ng#Pass")


def _update_request(email="example6@example.com"):
    return CustomerUpdateRequest(last_name="King", first_name="Ada", email=email, address="12 St James's Square")


async def _row_counts(persisted):
    """(users, customers, accounts) committed."""
    return await persisted.count(User), await persisted.count(Customer), await persisted.count(Account)


@pytest.fixture
def account_numbers(customer_service, monkeypatch):
    """Make the service use the given account numbers, in order, as if they had passed the "not in use" check (as
    happens when another operation takes a number between the check and the save)."""

    def _account_numbers(*numbers):
        queue = list(numbers)

        async def next_number(unit_of_work, account_type_id):
            return queue.pop(0) if len(queue) > 1 else queue[0]

        monkeypatch.setattr(customer_service, "_new_account_number_async", next_number)

    return _account_numbers


@pytest.fixture
def customer_without_accounts(customer_service, session_factory):
    """Create a customer and close its only account, so that it has no accounts and no transactions."""

    async def _customer_without_accounts():
        async with UnitOfWork(session_factory) as unit_of_work:
            created = await customer_service.create_customer(unit_of_work, _create_request())
            await customer_service.close_account(unit_of_work, created.user_id, created.accounts[0].account_number)
        return created

    return _customer_without_accounts


# ---------------------------------------------------------------------------
# Contract and dependency injection
# ---------------------------------------------------------------------------

def test_implements_its_interface():
    assert_implements(CustomerService, ICustomerService)


@pytest.mark.parametrize("name", operations(ICustomerService))
def test_every_operation_takes_the_callers_unit_of_work(name):
    assert_takes_the_unit_of_work_first(CustomerService, ICustomerService, name)


def test_user_service_is_injected():
    user_service = MagicMock(spec=IUserService)

    assert CustomerService(user_service).user_service is user_service


@pytest.mark.asyncio
class TestDependencies:
    """The customer service works through the injected user service and the caller's unit of work (mocks)."""

    async def test_create_customer_stages_the_user_through_the_user_service(self, mock_unit_of_work):
        user, role = User(Id=uuid.UUID(int=1), RoleId=AppConstants.CustomerRoleId), Role(Id=1, Name="Customer")
        user_service = MagicMock(spec=IUserService)
        user_service.stage_new_user = AsyncMock(return_value=(user, role))
        mock_unit_of_work.account_types.get_by_id_async.return_value = MagicMock(Id=1, Type="Savings")
        mock_unit_of_work.accounts.exists_async.return_value = False

        async def save_assigning_keys():  # what a flush does: the new rows get their keys and defaults
            for repository in (mock_unit_of_work.customers, mock_unit_of_work.accounts):
                repository.add_single.call_args.args[0].Id = uuid.uuid4()
            mock_unit_of_work.accounts.add_single.call_args.args[0].Active = True

        mock_unit_of_work.save_changes_async.side_effect = save_assigning_keys

        response = await CustomerService(user_service).create_customer(mock_unit_of_work, _create_request())

        unit_of_work, user_request = user_service.stage_new_user.await_args.args
        assert unit_of_work is mock_unit_of_work
        assert (user_request.email, user_request.role_id) == ("example5@example.com",
                                                              AppConstants.CustomerRoleId)
        customer = mock_unit_of_work.customers.add_single.call_args.args[0]
        account = mock_unit_of_work.accounts.add_single.call_args.args[0]
        assert (customer.user, customer.Address) == (user, "3 Navy Road")
        assert (account.user, account.AccountTypeId, account.Balance) == (user, 1, Decimal("0.00"))
        mock_unit_of_work.save_changes_async.assert_awaited_once()
        assert (response.customer_id, response.accounts[0].account_id) == (customer.Id, account.Id)

    async def test_nothing_is_staged_for_an_unknown_account_type(self, mock_unit_of_work):
        user_service = MagicMock(spec=IUserService)
        mock_unit_of_work.account_types.get_by_id_async.return_value = None

        with pytest.raises(NotFoundError):
            await CustomerService(user_service).create_customer(mock_unit_of_work, _create_request())

        user_service.stage_new_user.assert_not_called()
        mock_unit_of_work.save_changes_async.assert_not_awaited()


# ---------------------------------------------------------------------------
# create_customer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCreateCustomer:
    async def test_creates_the_user_the_customer_and_the_first_account_together(self, customer_service,
                                                                               unit_of_work, persisted, save_spy):
        response = await customer_service.create_customer(unit_of_work, _create_request())

        user = await persisted.get(User, response.user_id)
        customer = await persisted.get(Customer, response.customer_id)
        account = await persisted.get(Account, response.accounts[0].account_id)
        assert (user.Email, user.RoleId, customer.UserId, customer.Address) == \
            ("example5@example.com", AppConstants.CustomerRoleId, user.Id, "3 Navy Road")
        assert (account.UserId, account.AccountTypeId, account.Balance, account.Active) == \
            (user.Id, AppConstants.SavingsAccountTypeId, Decimal("0.00"), True)
        save_spy.assert_awaited_once()

    async def test_response_describes_the_new_customer(self, customer_service, unit_of_work):
        response = await customer_service.create_customer(unit_of_work, _create_request())

        assert isinstance(response, UserResponse)
        assert (response.role_id, response.role_name, response.address, response.active) == \
            (AppConstants.CustomerRoleId, "Customer", "3 Navy Road", True)
        assert len(response.accounts) == 1
        account = response.accounts[0]
        assert (account.account_type, account.balance, account.active) == ("Savings", Decimal("0.00"), True)

    @pytest.mark.parametrize("account_type_id, prefix", [(AppConstants.SavingsAccountTypeId, "26"),
                                                          (AppConstants.CurrentAccountTypeId, "20")],
                             ids=["savings", "current"])
    async def test_account_number_follows_the_account_type(self, customer_service, unit_of_work, account_type_id,
                                                           prefix):
        response = await customer_service.create_customer(unit_of_work,
                                                          _create_request(account_type_id=account_type_id))

        number = response.accounts[0].account_number
        assert len(number) == 10 and number.isdigit() and number.startswith(prefix)

    async def test_unknown_account_type_creates_nothing(self, customer_service, unit_of_work, persisted, save_spy):
        before = await _row_counts(persisted)

        with pytest.raises(NotFoundError, match="Account type with Id 99"):
            await customer_service.create_customer(unit_of_work, _create_request(account_type_id=99))

        assert await _row_counts(persisted) == before
        save_spy.assert_not_awaited()

    async def test_email_in_use_creates_nothing(self, customer_service, unit_of_work, persisted, save_spy):
        before = await _row_counts(persisted)

        with pytest.raises(ConflictError):
            await customer_service.create_customer(unit_of_work, _create_request(email="example1@example.com"))

        assert await _row_counts(persisted) == before
        save_spy.assert_not_awaited()

    async def test_failed_save_creates_nothing(self, customer_service, unit_of_work, persisted, failing_trigger):
        # The account insert is refused: the user and the customer record must not be kept either.
        await failing_trigger("BEFORE INSERT ON Accounts")
        before = await _row_counts(persisted)

        with pytest.raises(PersistenceError):
            await customer_service.create_customer(unit_of_work, _create_request())

        assert await _row_counts(persisted) == before


@pytest.mark.asyncio
class TestSaveConflicts:
    """Constraint violations reported by the database when saving (another operation got in between)."""

    async def test_taken_account_number_is_retried_with_a_new_one(self, customer_service, unit_of_work, persisted,
                                                                  account_numbers, save_spy):
        account_numbers(TAKEN_ACCOUNT_NUMBER, FREE_ACCOUNT_NUMBERS[0])
        before = await _row_counts(persisted)

        response = await customer_service.create_customer(unit_of_work, _create_request())

        assert response.accounts[0].account_number == FREE_ACCOUNT_NUMBERS[0]
        assert save_spy.await_count == 2
        # exactly one new user, customer and account: nothing of the failed attempt is left
        assert await _row_counts(persisted) == tuple(count + 1 for count in before)
        assert await persisted.count(User, User.Email == "example5@example.com") == 1

    async def test_gives_up_when_every_attempt_finds_the_number_taken(self, customer_service, unit_of_work,
                                                                     persisted, account_numbers, save_spy):
        account_numbers(TAKEN_ACCOUNT_NUMBER)
        before = await _row_counts(persisted)

        with pytest.raises(ConflictError) as exc_info:
            await customer_service.create_customer(unit_of_work, _create_request())

        assert exc_info.value.message == CONFLICT_MESSAGES[ACCOUNT_NUMBER_CONSTRAINT]
        assert save_spy.await_count == MAX_SAVE_ATTEMPTS
        assert await _row_counts(persisted) == before

    async def test_email_taken_meanwhile_is_reported_and_not_retried(self, customer_service, unit_of_work,
                                                                     persisted, monkeypatch, save_spy):
        monkeypatch.setattr(unit_of_work.users, "exists_async", AsyncMock(return_value=False))
        before = await _row_counts(persisted)

        with pytest.raises(ConflictError) as exc_info:
            await customer_service.create_customer(unit_of_work, _create_request(email="example2@example.com"))

        assert exc_info.value.message == "The email address is already in use."
        save_spy.assert_awaited_once()
        assert await _row_counts(persisted) == before

    async def test_open_account_retries_a_taken_account_number(self, customer_service, unit_of_work, bank,
                                                               account_numbers, save_spy):
        account_numbers(TAKEN_ACCOUNT_NUMBER, FREE_ACCOUNT_NUMBERS[1])

        account = await customer_service.open_account(unit_of_work, bank.user_ids["Ben"],
                                                      AppConstants.CurrentAccountTypeId)

        assert account.account_number == FREE_ACCOUNT_NUMBERS[1]
        assert save_spy.await_count == 2

    async def test_second_account_of_a_type_opened_meanwhile_is_reported(self, customer_service, unit_of_work,
                                                                         bank, monkeypatch, save_spy):
        # The "already has one" check passes, but the (UserId, AccountTypeId) unique key refuses the save.
        monkeypatch.setattr(unit_of_work.accounts, "exists_async", AsyncMock(return_value=False))
        customer_service._new_account_number_async = AsyncMock(return_value=FREE_ACCOUNT_NUMBERS[0])

        with pytest.raises(ConflictError) as exc_info:
            await customer_service.open_account(unit_of_work, bank.user_ids["Ben"],
                                                AppConstants.SavingsAccountTypeId)

        assert exc_info.value.message == "The customer already has an account of this account type."
        save_spy.assert_awaited_once()


@pytest.mark.asyncio
class TestNewAccountNumber:
    async def test_number_in_use_is_skipped(self, unit_of_work, monkeypatch):
        numbers = iter([TAKEN_ACCOUNT_NUMBER, "2600000003", FREE_ACCOUNT_NUMBERS[0]])
        monkeypatch.setattr(customer_service_module, "generate_account_number", lambda account_type_id: next(numbers))

        assert await CustomerService._new_account_number_async(unit_of_work, 1) == FREE_ACCOUNT_NUMBERS[0]

    async def test_gives_up_after_the_attempts(self, unit_of_work, monkeypatch):
        generated = []
        monkeypatch.setattr(customer_service_module, "generate_account_number",
                            lambda account_type_id: generated.append(account_type_id) or TAKEN_ACCOUNT_NUMBER)

        with pytest.raises(ConflictError):
            await CustomerService._new_account_number_async(unit_of_work, 2)

        assert generated == [2] * MAX_ACCOUNT_NUMBER_ATTEMPTS


# ---------------------------------------------------------------------------
# update_customer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestUpdateCustomer:
    async def test_updates_the_address_and_the_user_together(self, customer_service, unit_of_work, persisted, bank,
                                                             save_spy):
        response = await customer_service.update_customer(unit_of_work, bank.user_ids["Ada"], _update_request())

        user = await persisted.get(User, bank.user_ids["Ada"])
        customer = (await persisted.all(select(Customer).where(Customer.UserId == user.Id)))[0]
        assert (user.LastName, user.Email, customer.Address) == ("King", "example6@example.com",
                                                                 "12 St James's Square")
        assert (response.last_name, response.address, len(response.accounts)) == ("King", "12 St James's Square", 2)
        save_spy.assert_awaited_once()

    async def test_email_of_another_user_changes_nothing(self, customer_service, unit_of_work, persisted, bank):
        with pytest.raises(ConflictError):
            await customer_service.update_customer(unit_of_work, bank.user_ids["Ada"],
                                                   _update_request(email="example2@example.com"))

        customer = (await persisted.all(select(Customer).where(Customer.UserId == bank.user_ids["Ada"])))[0]
        assert customer.Address == "Ada Street"
        assert (await persisted.get(User, bank.user_ids["Ada"])).LastName == "Lovelace"

    @pytest.mark.parametrize("user", ["staff", "missing"])
    async def test_user_who_is_not_a_customer_is_not_found(self, customer_service, unit_of_work, bank, user):
        user_id = bank.user_ids["Dee"] if user == "staff" else MISSING_USER_ID

        with pytest.raises(NotFoundError):
            await customer_service.update_customer(unit_of_work, user_id, _update_request())


# ---------------------------------------------------------------------------
# delete_customer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDeleteCustomer:
    async def test_customer_with_accounts_is_restricted(self, customer_service, unit_of_work, persisted, bank,
                                                        save_spy):
        before = await _row_counts(persisted)

        with pytest.raises(DeleteRestrictedError, match="has accounts"):
            await customer_service.delete_customer(unit_of_work, bank.user_ids["Cy"])

        assert await _row_counts(persisted) == before
        save_spy.assert_not_awaited()

    async def test_customer_without_accounts_is_deleted_with_its_user(self, customer_service, unit_of_work,
                                                                      persisted, customer_without_accounts,
                                                                      save_spy):
        created = await customer_without_accounts()

        await customer_service.delete_customer(unit_of_work, created.user_id)

        assert await persisted.get(Customer, created.customer_id) is None
        assert await persisted.get(User, created.user_id) is None
        save_spy.assert_awaited_once()

    async def test_customer_who_is_also_staff_is_restricted(self, customer_service, unit_of_work, persisted,
                                                            customer_without_accounts):
        created = await customer_without_accounts()
        await unit_of_work.staff.add_single_async(Staff(UserId=created.user_id, Position="Teller"))

        with pytest.raises(DeleteRestrictedError, match="also a staff member"):
            await customer_service.delete_customer(unit_of_work, created.user_id)

        assert await persisted.get(Customer, created.customer_id) is not None

    @pytest.mark.parametrize("user", ["staff", "missing"])
    async def test_user_who_is_not_a_customer_is_not_found(self, customer_service, unit_of_work, bank, user):
        user_id = bank.user_ids["Dee"] if user == "staff" else MISSING_USER_ID

        with pytest.raises(NotFoundError):
            await customer_service.delete_customer(unit_of_work, user_id)


# ---------------------------------------------------------------------------
# deactivate_customer_account
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDeactivateCustomerAccount:
    async def test_deactivates_the_customer_and_every_account_in_one_save(self, customer_service, unit_of_work,
                                                                         persisted, bank, save_spy):
        response = await customer_service.deactivate_customer_account(unit_of_work, bank.user_ids["Ada"])

        assert (await persisted.get(User, bank.user_ids["Ada"])).Active is False
        accounts = await persisted.all(select(Account).where(Account.UserId == bank.user_ids["Ada"]))
        assert [account.Active for account in accounts] == [False, False]
        assert isinstance(response, UserResponse) and response.active is False
        assert [account.active for account in response.accounts] == [False, False]
        save_spy.assert_awaited_once()

    async def test_accounts_keep_their_balances(self, customer_service, unit_of_work, bank, balances):
        before = await balances()

        await customer_service.deactivate_customer_account(unit_of_work, bank.user_ids["Ada"])

        assert await balances() == before

    async def test_other_users_and_accounts_stay_active(self, customer_service, unit_of_work, persisted, bank):
        await customer_service.deactivate_customer_account(unit_of_work, bank.user_ids["Ada"])

        others = await persisted.all(select(Account).where(Account.UserId != bank.user_ids["Ada"]))
        assert others and all(account.Active for account in others)
        for name in ("Ben", "Cy", "Dee"):
            assert (await persisted.get(User, bank.user_ids[name])).Active is True

    async def test_deactivating_again_changes_nothing(self, customer_service, unit_of_work, persisted, bank):
        await customer_service.deactivate_customer_account(unit_of_work, bank.user_ids["Ada"])

        response = await customer_service.deactivate_customer_account(unit_of_work, bank.user_ids["Ada"])

        assert response.active is False
        accounts = await persisted.all(select(Account).where(Account.UserId == bank.user_ids["Ada"]))
        assert not any(account.Active for account in accounts)

    async def test_remaining_active_accounts_of_an_inactive_customer_are_deactivated(self, customer_service,
                                                                                     unit_of_work, persisted, bank,
                                                                                     user_service):
        await user_service.toggle_user_active_status(unit_of_work, bank.user_ids["Ben"])  # user inactive only

        await customer_service.deactivate_customer_account(unit_of_work, bank.user_ids["Ben"])

        accounts = await persisted.all(select(Account).where(Account.UserId == bank.user_ids["Ben"]))
        assert not any(account.Active for account in accounts)

    async def test_failed_save_deactivates_nothing(self, customer_service, unit_of_work, persisted, bank,
                                                   failing_trigger):
        # The accounts update is refused after the user's update was written: both are rolled back.
        await failing_trigger("BEFORE UPDATE OF Active ON Accounts")

        with pytest.raises(PersistenceError):
            await customer_service.deactivate_customer_account(unit_of_work, bank.user_ids["Ada"])

        assert (await persisted.get(User, bank.user_ids["Ada"])).Active is True
        accounts = await persisted.all(select(Account).where(Account.UserId == bank.user_ids["Ada"]))
        assert all(account.Active for account in accounts)

    @pytest.mark.parametrize("user", ["staff", "missing"])
    async def test_user_who_is_not_a_customer_is_not_found(self, customer_service, unit_of_work, persisted, bank,
                                                           user, save_spy):
        user_id = bank.user_ids["Dee"] if user == "staff" else MISSING_USER_ID

        with pytest.raises(NotFoundError):
            await customer_service.deactivate_customer_account(unit_of_work, user_id)

        assert (await persisted.get(User, bank.user_ids["Dee"])).Active is True
        save_spy.assert_not_awaited()


# ---------------------------------------------------------------------------
# get_all_customers / get_customer_by_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetCustomers:
    async def test_get_all_customers_returns_every_customer_sorted_by_name(self, customer_service, unit_of_work):
        customers = await customer_service.get_all_customers(unit_of_work)

        assert [customer.last_name for customer in customers] == ["Lovelace", "Okafor", "Young"]
        ada = customers[0]
        assert [(account.account_number, account.account_type, account.balance) for account in ada.accounts] == \
            [("2600000001", "Savings", Decimal("100.00")), ("2600000002", "Current", Decimal("50.00"))]
        assert all(customer.role_name == "Customer" and customer.customer_id for customer in customers)

    async def test_get_all_customers_sorts_through_one_join_and_loads_related_rows_separately(
            self, customer_service, unit_of_work, sql_statements):
        await customer_service.get_all_customers(unit_of_work)

        selects = [statement for statement in sql_statements if statement.startswith("SELECT")]
        list_query, users_query, accounts_query = selects
        assert list_query.count("JOIN") == 1 and "JOIN Users ON" in list_query
        assert "ORDER BY Users.LastName, Users.FirstName" in list_query
        assert "WHERE Users.Id IN (" in users_query
        assert "WHERE Accounts.UserId IN (" in accounts_query

    async def test_accounts_show_whether_they_are_active(self, customer_service, unit_of_work, bank,
                                                         deactivate_account):
        await deactivate_account("2600000002")

        response = await customer_service.get_customer_by_id(unit_of_work, bank.user_ids["Ada"])

        assert response.active is True
        assert [(account.account_number, account.active) for account in response.accounts] == \
            [("2600000001", True), ("2600000002", False)]

    async def test_get_customer_by_id(self, customer_service, unit_of_work, bank):
        response = await customer_service.get_customer_by_id(unit_of_work, bank.user_ids["Cy"])

        assert (response.first_name, response.address, response.role_name, response.active) == \
            ("Cy", "Cy Street", "Customer", True)
        assert [account.account_number for account in response.accounts] == ["2600000004"]

    @pytest.mark.parametrize("user", ["staff", "missing"])
    async def test_user_who_is_not_a_customer_is_not_found(self, customer_service, unit_of_work, bank, user):
        user_id = bank.user_ids["Dee"] if user == "staff" else MISSING_USER_ID

        with pytest.raises(NotFoundError):
            await customer_service.get_customer_by_id(unit_of_work, user_id)


# ---------------------------------------------------------------------------
# open_account / close_account
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestOpenAccount:
    async def test_opens_an_account_of_another_type(self, customer_service, unit_of_work, persisted, bank,
                                                    save_spy):
        response = await customer_service.open_account(unit_of_work, bank.user_ids["Ben"],
                                                       AppConstants.CurrentAccountTypeId)

        stored = await persisted.get(Account, response.account_id)
        assert isinstance(response, AccountsResponse)
        assert (stored.UserId, stored.AccountTypeId, stored.Balance, stored.Active) == \
            (bank.user_ids["Ben"], AppConstants.CurrentAccountTypeId, Decimal("0.00"), True)
        assert (response.account_type, response.balance, response.active) == ("Current", Decimal("0.00"), True)
        save_spy.assert_awaited_once()

    async def test_deactivated_customer_cannot_open_an_account(self, customer_service, unit_of_work, persisted,
                                                                bank):
        await customer_service.deactivate_customer_account(unit_of_work, bank.user_ids["Ben"])
        before = await persisted.count(Account)

        with pytest.raises(BusinessRuleError, match="is deactivated"):
            await customer_service.open_account(unit_of_work, bank.user_ids["Ben"],
                                                AppConstants.CurrentAccountTypeId)

        assert await persisted.count(Account) == before

    async def test_customer_whose_user_is_inactive_cannot_open_an_account(self, customer_service, user_service,
                                                                          unit_of_work, persisted, bank, save_spy):
        await user_service.toggle_user_active_status(unit_of_work, bank.user_ids["Ben"])
        save_spy.reset_mock()

        with pytest.raises(BusinessRuleError, match="is deactivated"):
            await customer_service.open_account(unit_of_work, bank.user_ids["Ben"],
                                                AppConstants.CurrentAccountTypeId)

        assert await persisted.count(Account, Account.UserId == bank.user_ids["Ben"]) == 1
        save_spy.assert_not_awaited()

    async def test_second_account_of_a_type_is_a_conflict(self, customer_service, unit_of_work, persisted, bank,
                                                          save_spy):
        before = await persisted.count(Account)

        with pytest.raises(ConflictError, match="already has a Savings account"):
            await customer_service.open_account(unit_of_work, bank.user_ids["Ben"],
                                                AppConstants.SavingsAccountTypeId)

        assert await persisted.count(Account) == before
        save_spy.assert_not_awaited()

    @pytest.mark.parametrize("user, account_type_id", [("missing", 2), ("staff", 1), ("Ben", 99)],
                             ids=["missing-customer", "staff-member", "missing-account-type"])
    async def test_missing_customer_or_account_type_is_not_found(self, customer_service, unit_of_work, bank,
                                                                 user, account_type_id):
        user_id = {"missing": MISSING_USER_ID, "staff": bank.user_ids["Dee"], "Ben": bank.user_ids["Ben"]}[user]

        with pytest.raises(NotFoundError):
            await customer_service.open_account(unit_of_work, user_id, account_type_id)


@pytest.mark.asyncio
class TestCloseAccount:
    async def test_closes_an_empty_account_without_transactions(self, customer_service, unit_of_work, persisted,
                                                                bank, save_spy):
        await customer_service.close_account(unit_of_work, bank.user_ids["Cy"], "2600000004")

        assert await persisted.get(Account, bank.account_id("2600000004")) is None
        save_spy.assert_awaited_once()

    async def test_account_with_a_balance_is_not_closed(self, customer_service, unit_of_work, persisted, bank,
                                                        save_spy):
        with pytest.raises(BusinessRuleError, match="still holds a balance"):
            await customer_service.close_account(unit_of_work, bank.user_ids["Ada"], "2600000002")

        assert await persisted.get(Account, bank.account_id("2600000002")) is not None
        save_spy.assert_not_awaited()

    async def test_account_with_transactions_is_restricted(self, customer_service, unit_of_work, persisted, bank,
                                                           add_transaction):
        await add_transaction("2600000004", amount="1.00")  # Cy's account: history, but still a zero balance

        with pytest.raises(DeleteRestrictedError, match="has transactions"):
            await customer_service.close_account(unit_of_work, bank.user_ids["Cy"], "2600000004")

        assert await persisted.get(Account, bank.account_id("2600000004")) is not None

    async def test_account_of_another_customer_is_not_found(self, customer_service, unit_of_work, persisted, bank):
        with pytest.raises(NotFoundError, match="has no account with this account number"):
            await customer_service.close_account(unit_of_work, bank.user_ids["Ben"], "2600000004")

        assert await persisted.get(Account, bank.account_id("2600000004")) is not None

    @pytest.mark.parametrize("account_number", ["26000", "abcdefghij", ""], ids=["short", "letters", "empty"])
    async def test_invalid_account_number_is_rejected(self, customer_service, unit_of_work, bank, account_number):
        with pytest.raises(InvalidInputError, match="account number"):
            await customer_service.close_account(unit_of_work, bank.user_ids["Cy"], account_number)

    async def test_missing_customer_is_not_found(self, customer_service, unit_of_work):
        with pytest.raises(NotFoundError):
            await customer_service.close_account(unit_of_work, MISSING_USER_ID, "2600000004")

    async def test_customer_can_be_deleted_once_its_accounts_are_closed(self, customer_service, unit_of_work,
                                                                        persisted, bank):
        await customer_service.close_account(unit_of_work, bank.user_ids["Cy"], "2600000004")

        await customer_service.delete_customer(unit_of_work, bank.user_ids["Cy"])

        assert await persisted.get(User, bank.user_ids["Cy"]) is None


# ---------------------------------------------------------------------------
# Error messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_messages_do_not_contain_account_numbers_or_email_addresses(customer_service, unit_of_work, bank,
                                                                                add_transaction, account_numbers,
                                                                                monkeypatch):
    messages = []

    async def message_of(operation):
        with pytest.raises(ServiceError) as exc_info:
            await operation
        messages.append(exc_info.value.message)

    await message_of(customer_service.create_customer(unit_of_work, _create_request(email="example1@example.com")))
    await message_of(customer_service.update_customer(unit_of_work, bank.user_ids["Ben"],
                                                      _update_request(email="example1@example.com")))
    await message_of(customer_service.close_account(unit_of_work, bank.user_ids["Ada"], "2600000002"))
    await message_of(customer_service.close_account(unit_of_work, bank.user_ids["Ben"], "2600000004"))
    await add_transaction("2600000004", amount="1.00")
    await message_of(customer_service.close_account(unit_of_work, bank.user_ids["Cy"], "2600000004"))
    account_numbers(TAKEN_ACCOUNT_NUMBER)
    await message_of(customer_service.open_account(unit_of_work, bank.user_ids["Ben"],
                                                   AppConstants.CurrentAccountTypeId))
    monkeypatch.setattr(unit_of_work.users, "exists_async", AsyncMock(return_value=False))
    await message_of(customer_service.create_customer(unit_of_work, _create_request(email="example2@example.com")))

    assert len(messages) == 7
    for message in messages:
        assert_no_personal_data(message)
