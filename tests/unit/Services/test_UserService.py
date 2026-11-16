"""UserService (Services/Implementations/UserService.py), run through a unit of work on the SQLite test database.

The `bank` rows (tests/unit/Data/conftest.py): customers Ada, Ben and Cy and staff member Dee, each with accounts;
Ada's and Ben's savings accounts have a deposit.
"""
import uuid
from unittest.mock import AsyncMock

import pytest

from Data.Implementations.unit_of_work import UnitOfWork
from Infrastructure.Security import verify_password
from Models.Constants.AppConstants import AppConstants
from Models.Dtos.Request.UpdateUserRequest import UpdateUserRequest
from Models.Dtos.Request.UserRequest import UserRequest
from Models.Dtos.Response.UserResponse import UserResponse
from Models.Entities import Account, Role, User
from Services.Exceptions.domain_exceptions import ConflictError, DeleteRestrictedError, NotFoundError
from Services.Implementations import UserService as user_service_module
from Services.Implementations.UserService import UserService
from Services.Interfaces.i_user_service import IUserService
from tests.unit.Services.conftest import SERVICE_TEST_MARKS
from tests.unit.Services.service_contract import assert_implements, assert_takes_the_unit_of_work_first, operations

pytestmark = SERVICE_TEST_MARKS

MISSING_USER_ID = uuid.UUID(int=404)


def _user_request(email="example10@example.com", role_id=AppConstants.CustomerRoleId):
    return UserRequest(last_name="Turing", first_name="Alan", email=email, role_id=role_id, password="Str0ng#Pass")


def _update_request(email="example8@example.com"):
    return UpdateUserRequest(last_name="Turing", first_name="Alan", email=email)


async def _user_count(persisted):
    return await persisted.count(User)


@pytest.fixture
def created_user_id(user_service, session_factory):
    """Create a user with no staff or customer record, accounts or transactions (in a unit of work of its own)."""

    async def _created_user_id(email="example11@example.com"):
        async with UnitOfWork(session_factory) as unit_of_work:
            return await user_service.create_user(unit_of_work, _user_request(email=email))

    return _created_user_id


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------

def test_implements_its_interface():
    assert_implements(UserService, IUserService)


@pytest.mark.parametrize("name", operations(IUserService))
def test_every_operation_takes_the_callers_unit_of_work(name):
    assert_takes_the_unit_of_work_first(UserService, IUserService, name)


# ---------------------------------------------------------------------------
# create_user / stage_new_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCreateUser:
    async def test_creates_the_user_and_returns_its_id(self, user_service, unit_of_work, persisted, save_spy):
        user_id = await user_service.create_user(unit_of_work, _user_request())

        stored = await persisted.get(User, user_id)
        assert isinstance(user_id, uuid.UUID)
        assert (stored.LastName, stored.FirstName, stored.Email, stored.RoleId, stored.Active) == \
            ("Turing", "Alan", "example10@example.com", AppConstants.CustomerRoleId, True)
        save_spy.assert_awaited_once()

    async def test_password_is_stored_hashed(self, user_service, unit_of_work, persisted):
        user_id = await user_service.create_user(unit_of_work, _user_request())

        stored = await persisted.get(User, user_id)
        assert stored.Password != "Str0ng#Pass"
        assert verify_password("Str0ng#Pass", stored.Password)

    async def test_password_is_hashed_at_the_configured_cost(self, user_service, unit_of_work, persisted):
        # BCRYPT_ROUNDS is 4 in these tests (conftest.py); a bcrypt hash records its cost.
        user_id = await user_service.create_user(unit_of_work, _user_request())

        assert (await persisted.get(User, user_id)).Password.startswith("$2b$04$")

    async def test_password_is_hashed_without_blocking_the_event_loop(self, user_service, unit_of_work, persisted,
                                                                      monkeypatch):
        hashing = AsyncMock(return_value="hashed-off-the-event-loop")
        monkeypatch.setattr(user_service_module, "hash_password_async", hashing)

        user_id = await user_service.create_user(unit_of_work, _user_request())

        hashing.assert_awaited_once_with("Str0ng#Pass")
        assert (await persisted.get(User, user_id)).Password == "hashed-off-the-event-loop"

    async def test_email_in_use_is_a_conflict_and_nothing_is_saved(self, user_service, unit_of_work, persisted,
                                                                   save_spy):
        before = await _user_count(persisted)

        with pytest.raises(ConflictError) as exc_info:
            await user_service.create_user(unit_of_work, _user_request(email="example1@example.com"))

        assert exc_info.value.message == "The email address is already in use."  # without the address

        assert await _user_count(persisted) == before
        save_spy.assert_not_awaited()

    async def test_unknown_role_is_not_found(self, user_service, unit_of_work, persisted, save_spy):
        before = await _user_count(persisted)

        with pytest.raises(NotFoundError, match="Role with Id 99"):
            await user_service.create_user(unit_of_work, _user_request(role_id=99))

        assert await _user_count(persisted) == before
        save_spy.assert_not_awaited()

    async def test_email_taken_between_the_check_and_the_save_is_a_conflict(self, user_service, unit_of_work,
                                                                            persisted, monkeypatch):
        # Another operation registers the address after the check: the database's unique key refuses the save.
        monkeypatch.setattr(unit_of_work.users, "exists_async", AsyncMock(return_value=False))
        before = await _user_count(persisted)

        with pytest.raises(ConflictError, match="already in use") as exc_info:
            await user_service.create_user(unit_of_work, _user_request(email="example2@example.com"))

        assert type(exc_info.value.__cause__).__name__ == "IntegrityError"
        assert await _user_count(persisted) == before

    async def test_stage_new_user_stages_without_saving(self, user_service, unit_of_work, persisted, save_spy):
        before = await _user_count(persisted)

        user, role = await user_service.stage_new_user(unit_of_work, _user_request())

        assert isinstance(user, User) and isinstance(role, Role)
        assert (role.Id, role.Name, user.RoleId) == (AppConstants.CustomerRoleId, "Customer",
                                                      AppConstants.CustomerRoleId)
        assert verify_password("Str0ng#Pass", user.Password)
        assert await _user_count(persisted) == before
        save_spy.assert_not_awaited()

        await unit_of_work.save_changes_async()  # the caller saves

        assert (await persisted.get(User, user.Id)).Email == "example10@example.com"


# ---------------------------------------------------------------------------
# toggle_user_active_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestToggleActiveStatus:
    async def test_deactivates_an_active_user(self, user_service, unit_of_work, persisted, bank, save_spy):
        assert await user_service.toggle_user_active_status(unit_of_work, bank.user_ids["Ben"]) is False

        assert (await persisted.get(User, bank.user_ids["Ben"])).Active is False
        save_spy.assert_awaited_once()

    async def test_activates_an_inactive_user(self, user_service, unit_of_work, persisted, bank):
        await user_service.toggle_user_active_status(unit_of_work, bank.user_ids["Ben"])

        assert await user_service.toggle_user_active_status(unit_of_work, bank.user_ids["Ben"]) is True
        assert (await persisted.get(User, bank.user_ids["Ben"])).Active is True

    async def test_missing_user_is_not_found(self, user_service, unit_of_work, save_spy):
        with pytest.raises(NotFoundError):
            await user_service.toggle_user_active_status(unit_of_work, MISSING_USER_ID)

        save_spy.assert_not_awaited()


# ---------------------------------------------------------------------------
# update_user / stage_user_update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestUpdateUser:
    async def test_updates_the_names_and_email(self, user_service, unit_of_work, persisted, bank, save_spy):
        response = await user_service.update_user(unit_of_work, bank.user_ids["Ben"], _update_request())

        stored = await persisted.get(User, bank.user_ids["Ben"])
        assert (stored.LastName, stored.FirstName, stored.Email) == ("Turing", "Alan", "example8@example.com")
        assert isinstance(response, UserResponse)
        assert (response.user_id, response.email, response.role_name) == (bank.user_ids["Ben"],
                                                                          "example8@example.com", "Customer")
        save_spy.assert_awaited_once()

    async def test_keeping_the_own_email_is_allowed(self, user_service, unit_of_work, persisted, bank):
        await user_service.update_user(unit_of_work, bank.user_ids["Ben"], _update_request(email="example2@example.com"))

        assert (await persisted.get(User, bank.user_ids["Ben"])).LastName == "Turing"

    async def test_email_of_another_user_is_a_conflict_and_nothing_changes(self, user_service, unit_of_work,
                                                                           persisted, bank, save_spy):
        with pytest.raises(ConflictError):
            await user_service.update_user(unit_of_work, bank.user_ids["Ben"],
                                           _update_request(email="example1@example.com"))

        stored = await persisted.get(User, bank.user_ids["Ben"])
        assert (stored.LastName, stored.Email) == ("Okafor", "example2@example.com")
        save_spy.assert_not_awaited()

    async def test_missing_user_is_not_found(self, user_service, unit_of_work):
        with pytest.raises(NotFoundError):
            await user_service.update_user(unit_of_work, MISSING_USER_ID, _update_request())

    async def test_stage_user_update_stages_without_saving(self, user_service, unit_of_work, persisted, bank,
                                                           save_spy):
        user = await unit_of_work.users.get_by_id_async(bank.user_ids["Ben"])

        staged = await user_service.stage_user_update(unit_of_work, user, _update_request())

        assert staged is user and user.Email == "example8@example.com"
        assert (await persisted.get(User, bank.user_ids["Ben"])).Email == "example2@example.com"
        save_spy.assert_not_awaited()


# ---------------------------------------------------------------------------
# delete_user / ensure_user_can_be_deleted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDeleteUser:
    async def test_deletes_a_user_without_records_accounts_or_transactions(self, user_service, unit_of_work,
                                                                          persisted, created_user_id, save_spy):
        user_id = await created_user_id()

        await user_service.delete_user(unit_of_work, user_id)

        assert await persisted.get(User, user_id) is None
        save_spy.assert_awaited_once()

    @pytest.mark.parametrize("name, record", [("Ada", "customer"), ("Dee", "staff")])
    async def test_user_with_a_customer_or_staff_record_is_restricted(self, user_service, unit_of_work, persisted,
                                                                      bank, name, record, save_spy):
        with pytest.raises(DeleteRestrictedError, match="staff or customer record"):
            await user_service.delete_user(unit_of_work, bank.user_ids[name])

        assert await persisted.get(User, bank.user_ids[name]) is not None
        save_spy.assert_not_awaited()

    async def test_user_with_accounts_is_restricted(self, user_service, unit_of_work, persisted, bank,
                                                    created_user_id):
        user_id = await created_user_id()
        await unit_of_work.accounts.add_single_async(Account(UserId=user_id,
                                                             AccountTypeId=bank.account_type_ids["Savings"],
                                                             AccountNumber="2690000001"))

        with pytest.raises(DeleteRestrictedError, match="has accounts"):
            await user_service.delete_user(unit_of_work, user_id)

        assert await persisted.get(User, user_id) is not None

    async def test_user_who_sent_money_is_restricted(self, user_service, unit_of_work, persisted,
                                                     created_user_id, add_transaction):
        user_id = await created_user_id()
        await add_transaction("2600000001", sender=user_id)

        with pytest.raises(DeleteRestrictedError, match="has transactions"):
            await user_service.delete_user(unit_of_work, user_id)

        assert await persisted.get(User, user_id) is not None

    async def test_missing_user_is_not_found(self, user_service, unit_of_work):
        with pytest.raises(NotFoundError):
            await user_service.delete_user(unit_of_work, MISSING_USER_ID)

    @pytest.mark.parametrize("name", ["Ada", "Ben", "Dee"])
    async def test_owner_of_accounts_cannot_be_deleted(self, user_service, unit_of_work, bank, name):
        with pytest.raises(DeleteRestrictedError):
            await user_service.ensure_user_can_be_deleted(unit_of_work, bank.user_ids[name])

    async def test_user_without_accounts_or_transactions_can_be_deleted(self, user_service, unit_of_work,
                                                                        created_user_id, persisted):
        user_id = await created_user_id()

        assert await user_service.ensure_user_can_be_deleted(unit_of_work, user_id) is None
        assert await persisted.count(User, User.Id == user_id) == 1
