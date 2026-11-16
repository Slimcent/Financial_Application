"""AccountService (Services/Implementations/AccountService.py), run through a unit of work on the SQLite test
database.

The `bank` rows (tests/unit/Data/conftest.py):

    account      owner  type     balance
    2600000001   Ada    Savings  100.00
    2600000002   Ada    Current   50.00
    2600000003   Ben    Savings  200.00
    2600000004   Cy     Savings    0.00
    2600000005   Dee    Current   75.00    (Dee is staff; Ada, Ben and Cy are customers)
"""
import uuid
from decimal import Decimal

import pytest

from Models.Constants.AppConstants import AppConstants
from Models.Dtos.Response.AccountResponse import AccountResponse
from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Request.UserRequest import UserRequest
from Services.Exceptions.domain_exceptions import InvalidInputError, NotFoundError
from Services.Implementations.AccountService import AccountService
from Services.Interfaces.i_account_service import IAccountService
from tests.unit.Services.conftest import SERVICE_TEST_MARKS, assert_no_personal_data
from tests.unit.Services.service_contract import assert_implements, assert_takes_the_unit_of_work_first, operations

pytestmark = SERVICE_TEST_MARKS

MISSING_USER_ID = uuid.UUID(int=404)


def _summary(response):
    return [(account.account_number, account.account_type, account.balance) for account in response.accounts]


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------

def test_implements_its_interface():
    assert_implements(AccountService, IAccountService)


@pytest.mark.parametrize("name", operations(IAccountService))
def test_every_operation_takes_the_callers_unit_of_work(name):
    assert_takes_the_unit_of_work_first(AccountService, IAccountService, name)


# ---------------------------------------------------------------------------
# get_all_customer_accounts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetAllCustomerAccounts:
    async def test_every_customer_with_its_accounts_sorted_by_name(self, account_service, unit_of_work, bank,
                                                                   save_spy):
        responses = await account_service.get_all_customer_accounts(unit_of_work)

        assert all(isinstance(response, AccountResponse) for response in responses)
        assert [(response.last_name, response.total_balance) for response in responses] == \
            [("Lovelace", Decimal("150.00")), ("Okafor", Decimal("200.00")), ("Young", Decimal("0.00"))]
        assert _summary(responses[0]) == [("2600000001", "Savings", Decimal("100.00")),
                                          ("2600000002", "Current", Decimal("50.00"))]
        assert responses[0].customer_id is not None and responses[0].address == "Ada Street"
        save_spy.assert_not_awaited()

    async def test_holders_and_accounts_show_whether_they_are_active(self, account_service, customer_service,
                                                                     unit_of_work, bank):
        await customer_service.deactivate_customer_account(unit_of_work, bank.user_ids["Ben"])

        responses = {response.last_name: response
                     for response in await account_service.get_all_customer_accounts(unit_of_work)}

        assert (responses["Okafor"].active, [account.active for account in responses["Okafor"].accounts]) == \
            (False, [False])
        assert (responses["Lovelace"].active, [account.active for account in responses["Lovelace"].accounts]) == \
            (True, [True, True])

    async def test_staff_members_are_not_customers(self, account_service, unit_of_work, bank):
        responses = await account_service.get_all_customer_accounts(unit_of_work)

        assert bank.user_ids["Dee"] not in {response.user_id for response in responses}

    async def test_customer_without_accounts_is_listed_with_a_zero_total(self, account_service, customer_service,
                                                                         unit_of_work, bank):
        await customer_service.close_account(unit_of_work, bank.user_ids["Cy"], "2600000004")

        responses = await account_service.get_all_customer_accounts(unit_of_work)

        cy = next(response for response in responses if response.user_id == bank.user_ids["Cy"])
        assert (cy.accounts, cy.total_balance) == ([], Decimal("0.00"))


# ---------------------------------------------------------------------------
# get_customer_account_details
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetCustomerAccountDetails:
    async def test_one_account_with_its_owner(self, account_service, unit_of_work, bank):
        response = await account_service.get_customer_account_details(unit_of_work, bank.user_ids["Ada"],
                                                                      AppConstants.CurrentAccountTypeId)

        assert (response.user_id, response.first_name, response.address) == (bank.user_ids["Ada"], "Ada",
                                                                              "Ada Street")
        assert _summary(response) == [("2600000002", "Current", Decimal("50.00"))]
        assert (response.balance, response.total_balance) == (Decimal("50.00"), Decimal("50.00"))
        assert (response.active, response.accounts[0].active) == (True, True)

    async def test_staff_members_account_has_no_customer_details(self, account_service, unit_of_work, bank):
        response = await account_service.get_customer_account_details(unit_of_work, bank.user_ids["Dee"],
                                                                      AppConstants.CurrentAccountTypeId)

        assert (response.customer_id, response.address, response.balance) == (None, None, Decimal("75.00"))

    @pytest.mark.parametrize("user, account_type_id", [("Cy", AppConstants.CurrentAccountTypeId), ("missing", 1)],
                             ids=["no-account-of-the-type", "missing-user"])
    async def test_missing_account_is_not_found(self, account_service, unit_of_work, bank, user, account_type_id):
        user_id = bank.user_ids.get(user, MISSING_USER_ID)

        with pytest.raises(NotFoundError):
            await account_service.get_customer_account_details(unit_of_work, user_id, account_type_id)


# ---------------------------------------------------------------------------
# get_customer_accounts_with_user_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetCustomerAccountsWithUserId:
    async def test_every_account_of_the_user_and_the_total(self, account_service, unit_of_work, bank):
        response = await account_service.get_customer_accounts_with_user_id(unit_of_work, bank.user_ids["Ada"])

        assert _summary(response) == [("2600000001", "Savings", Decimal("100.00")),
                                      ("2600000002", "Current", Decimal("50.00"))]
        assert (response.total_balance, response.balance) == (Decimal("150.00"), None)

    async def test_user_without_accounts_has_a_zero_total(self, account_service, user_service, unit_of_work):
        user_id = await user_service.create_user(unit_of_work, UserRequest(
            last_name="Turing", first_name="Alan", email="example9@example.com", role_id=1, password="Str0ng#Pass"))

        response = await account_service.get_customer_accounts_with_user_id(unit_of_work, user_id)

        assert (response.accounts, response.total_balance, response.customer_id) == ([], Decimal("0.00"), None)

    async def test_missing_user_is_not_found(self, account_service, unit_of_work):
        with pytest.raises(NotFoundError):
            await account_service.get_customer_accounts_with_user_id(unit_of_work, MISSING_USER_ID)


# ---------------------------------------------------------------------------
# get_account_details_by_account_number
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetAccountDetailsByAccountNumber:
    async def test_the_account(self, account_service, unit_of_work, bank):
        response = await account_service.get_account_details_by_account_number(unit_of_work, "2600000003")

        assert isinstance(response, AccountsResponse)
        assert response.model_dump() == {"account_id": bank.account_id("2600000003"), "account_number": "2600000003",
                                         "balance": Decimal("200.00"), "account_type_id": 1,
                                         "account_type": "Savings", "active": True}

    async def test_deactivated_account_is_shown_as_inactive(self, account_service, unit_of_work,
                                                            deactivate_account):
        await deactivate_account("2600000003")

        response = await account_service.get_account_details_by_account_number(unit_of_work, "2600000003")

        assert response.active is False

    async def test_account_number_is_trimmed(self, account_service, unit_of_work):
        response = await account_service.get_account_details_by_account_number(unit_of_work, " 2600000003 ")

        assert response.account_number == "2600000003"

    async def test_missing_account_is_not_found(self, account_service, unit_of_work):
        with pytest.raises(NotFoundError) as exc_info:
            await account_service.get_account_details_by_account_number(unit_of_work, "2699999999")

        assert_no_personal_data(exc_info.value.message)

    @pytest.mark.parametrize("account_number", ["123", "26000000011", "26000x0001", ""],
                             ids=["short", "long", "letter", "empty"])
    async def test_invalid_account_number_is_rejected(self, account_service, unit_of_work, account_number):
        with pytest.raises(InvalidInputError, match="Invalid account number"):
            await account_service.get_account_details_by_account_number(unit_of_work, account_number)
