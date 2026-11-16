"""AccountTypeService (Services/Implementations/AccountTypeService.py), run through a unit of work on the SQLite test
database. The `bank` account types: Savings (1) and Current (2), used by accounts, and Retirement (3), unused."""
from unittest.mock import AsyncMock

import pytest

from Models.Dtos.Request.AccountTypeRequest import AccountTypeRequest
from Models.Dtos.Response.AccountTypeResponse import AccountTypeResponse
from Models.Entities import AccountType
from Services.Exceptions.domain_exceptions import ConflictError, DeleteRestrictedError, NotFoundError
from Services.Implementations.AccountTypeService import AccountTypeService
from Services.Interfaces.i_account_type_service import IAccountTypeService
from tests.unit.Services.conftest import SERVICE_TEST_MARKS
from tests.unit.Services.service_contract import assert_implements, assert_takes_the_unit_of_work_first, operations

pytestmark = SERVICE_TEST_MARKS

MISSING_ACCOUNT_TYPE_ID = 99


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------

def test_implements_its_interface():
    assert_implements(AccountTypeService, IAccountTypeService)


@pytest.mark.parametrize("name", operations(IAccountTypeService))
def test_every_operation_takes_the_callers_unit_of_work(name):
    assert_takes_the_unit_of_work_first(AccountTypeService, IAccountTypeService, name)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetAccountTypes:
    async def test_get_all_returns_every_account_type_by_id(self, account_type_service, unit_of_work, save_spy):
        account_types = await account_type_service.get_all_account_types(unit_of_work)

        assert all(isinstance(account_type, AccountTypeResponse) for account_type in account_types)
        assert [(item.account_type_id, item.name) for item in account_types] == \
            [(1, "Savings"), (2, "Current"), (3, "Retirement")]
        save_spy.assert_not_awaited()

    async def test_get_by_id(self, account_type_service, unit_of_work):
        response = await account_type_service.get_account_type_by_id(unit_of_work, 2)

        assert (response.account_type_id, response.name) == (2, "Current")

    async def test_missing_account_type_is_not_found(self, account_type_service, unit_of_work):
        with pytest.raises(NotFoundError, match=f"Id {MISSING_ACCOUNT_TYPE_ID}"):
            await account_type_service.get_account_type_by_id(unit_of_work, MISSING_ACCOUNT_TYPE_ID)


# ---------------------------------------------------------------------------
# add_account_type
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestAddAccountType:
    async def test_adds_the_account_type_and_returns_its_new_id(self, account_type_service, unit_of_work, persisted,
                                                                save_spy):
        response = await account_type_service.add_account_type(unit_of_work, AccountTypeRequest(name="Fixed Deposit"))

        assert (response.account_type_id, response.name) == (4, "Fixed Deposit")
        assert (await persisted.get(AccountType, 4)).Type == "Fixed Deposit"
        save_spy.assert_awaited_once()

    async def test_name_in_use_is_a_conflict(self, account_type_service, unit_of_work, persisted, save_spy):
        with pytest.raises(ConflictError, match="'Savings' already exists"):
            await account_type_service.add_account_type(unit_of_work, AccountTypeRequest(name="Savings"))

        assert await persisted.count(AccountType) == 3
        save_spy.assert_not_awaited()

    async def test_name_taken_between_the_check_and_the_save_is_a_conflict(self, account_type_service, unit_of_work,
                                                                           persisted, monkeypatch):
        monkeypatch.setattr(unit_of_work.account_types, "exists_async", AsyncMock(return_value=False))

        with pytest.raises(ConflictError, match="'Current' already exists") as exc_info:
            await account_type_service.add_account_type(unit_of_work, AccountTypeRequest(name="Current"))

        assert type(exc_info.value.__cause__).__name__ == "IntegrityError"
        assert await persisted.count(AccountType) == 3


# ---------------------------------------------------------------------------
# update_account_type
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestUpdateAccountType:
    async def test_renames_the_account_type(self, account_type_service, unit_of_work, persisted, save_spy):
        response = await account_type_service.update_account_type(unit_of_work, 3, AccountTypeRequest(name="Pension"))

        assert (response.account_type_id, response.name) == (3, "Pension")
        assert (await persisted.get(AccountType, 3)).Type == "Pension"
        save_spy.assert_awaited_once()

    async def test_keeping_the_own_name_is_allowed(self, account_type_service, unit_of_work):
        response = await account_type_service.update_account_type(unit_of_work, 3,
                                                                  AccountTypeRequest(name="Retirement"))

        assert response.name == "Retirement"

    async def test_name_of_another_account_type_is_a_conflict(self, account_type_service, unit_of_work, persisted,
                                                              save_spy):
        with pytest.raises(ConflictError):
            await account_type_service.update_account_type(unit_of_work, 3, AccountTypeRequest(name="Savings"))

        assert (await persisted.get(AccountType, 3)).Type == "Retirement"
        save_spy.assert_not_awaited()

    async def test_missing_account_type_is_not_found(self, account_type_service, unit_of_work, save_spy):
        with pytest.raises(NotFoundError):
            await account_type_service.update_account_type(unit_of_work, MISSING_ACCOUNT_TYPE_ID,
                                                           AccountTypeRequest(name="Pension"))

        save_spy.assert_not_awaited()


# ---------------------------------------------------------------------------
# delete_account_type
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDeleteAccountType:
    async def test_deletes_an_unused_account_type(self, account_type_service, unit_of_work, persisted, save_spy):
        await account_type_service.delete_account_type(unit_of_work, 3)

        assert await persisted.get(AccountType, 3) is None
        save_spy.assert_awaited_once()

    @pytest.mark.parametrize("account_type_id, name", [(1, "Savings"), (2, "Current")])
    async def test_account_type_used_by_accounts_is_restricted(self, account_type_service, unit_of_work, persisted,
                                                               account_type_id, name, save_spy):
        with pytest.raises(DeleteRestrictedError, match=f"'{name}' is used by accounts"):
            await account_type_service.delete_account_type(unit_of_work, account_type_id)

        assert await persisted.get(AccountType, account_type_id) is not None
        save_spy.assert_not_awaited()

    async def test_account_type_used_meanwhile_is_restricted(self, account_type_service, unit_of_work, persisted,
                                                             monkeypatch):
        # The "in use" check passes, but the foreign key of the accounts refuses the delete.
        monkeypatch.setattr(unit_of_work.accounts, "exists_async", AsyncMock(return_value=False))

        with pytest.raises(DeleteRestrictedError):
            await account_type_service.delete_account_type(unit_of_work, 1)

        assert await persisted.get(AccountType, 1) is not None

    async def test_missing_account_type_is_not_found(self, account_type_service, unit_of_work):
        with pytest.raises(NotFoundError):
            await account_type_service.delete_account_type(unit_of_work, MISSING_ACCOUNT_TYPE_ID)
