"""StaffService (Services/Implementations/StaffService.py), run through a unit of work on the SQLite test database.

Dee is the only staff member of the `bank` rows (a teller who also owns account 2600000005).
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from Models.Constants.AppConstants import AppConstants
from Models.Dtos.Request.StaffCreateRequest import StaffCreateRequest
from Models.Dtos.Request.StaffUpdateRequest import StaffUpdateRequest
from Models.Dtos.Response.UserResponse import UserResponse
from Models.Entities import Customer, Role, Staff, User
from Services.Exceptions.domain_exceptions import (ConflictError, DeleteRestrictedError, NotFoundError,
                                                   PersistenceError)
from Services.Implementations.StaffService import StaffService
from Services.Interfaces.i_staff_service import IStaffService
from Services.Interfaces.i_user_service import IUserService
from tests.unit.Services.conftest import SERVICE_TEST_MARKS
from tests.unit.Services.service_contract import assert_implements, assert_takes_the_unit_of_work_first, operations

pytestmark = SERVICE_TEST_MARKS

MISSING_USER_ID = uuid.UUID(int=404)


def _create_request(email="example5@example.com", last_name="Hopper"):
    return StaffCreateRequest(last_name=last_name, first_name="Grace", email=email, position="Manager",
                              password="Str0ng#Pass")


def _update_request(email="example7@example.com"):
    return StaffUpdateRequest(last_name="Mensah-Ofori", first_name="Dee", email=email, position="Head Teller")


async def _staff_and_user_counts(persisted):
    return await persisted.count(Staff), await persisted.count(User)


# ---------------------------------------------------------------------------
# Contract and dependency injection
# ---------------------------------------------------------------------------

def test_implements_its_interface():
    assert_implements(StaffService, IStaffService)


@pytest.mark.parametrize("name", operations(IStaffService))
def test_every_operation_takes_the_callers_unit_of_work(name):
    assert_takes_the_unit_of_work_first(StaffService, IStaffService, name)


def test_user_service_is_injected():
    user_service = MagicMock(spec=IUserService)

    assert StaffService(user_service).user_service is user_service


@pytest.mark.asyncio
class TestDependencies:
    """The staff service works through the injected user service and the caller's unit of work (mocks)."""

    async def test_create_staff_stages_the_user_through_the_user_service(self, mock_unit_of_work):
        user, role = User(Id=uuid.UUID(int=1), RoleId=AppConstants.StaffRoleId), Role(Id=2, Name="Staff")
        user_service = MagicMock(spec=IUserService)
        user_service.stage_new_user = AsyncMock(return_value=(user, role))

        response = await StaffService(user_service).create_staff(mock_unit_of_work, _create_request())

        unit_of_work, user_request = user_service.stage_new_user.await_args.args
        assert unit_of_work is mock_unit_of_work
        assert (user_request.email, user_request.role_id) == ("example5@example.com", AppConstants.StaffRoleId)
        staff = mock_unit_of_work.staff.add_single.call_args.args[0]
        assert (staff.User, staff.Position) == (user, "Manager")
        mock_unit_of_work.save_changes_async.assert_awaited_once()
        assert (response.user_id, response.role_name, response.position) == (user.Id, "Staff", "Manager")

    async def test_nothing_is_saved_when_the_user_service_refuses(self, mock_unit_of_work):
        user_service = MagicMock(spec=IUserService)
        user_service.stage_new_user = AsyncMock(side_effect=ConflictError("email in use"))

        with pytest.raises(ConflictError):
            await StaffService(user_service).create_staff(mock_unit_of_work, _create_request())

        mock_unit_of_work.staff.add_single.assert_not_called()
        mock_unit_of_work.save_changes_async.assert_not_awaited()

    async def test_toggle_delegates_to_the_user_service(self, mock_unit_of_work):
        user_service = MagicMock(spec=IUserService)
        user_service.toggle_user_active_status = AsyncMock(return_value=False)
        mock_unit_of_work.staff.exists_async.return_value = True

        assert await StaffService(user_service).toggle_staff_active_status(mock_unit_of_work,
                                                                           MISSING_USER_ID) is False
        user_service.toggle_user_active_status.assert_awaited_once_with(mock_unit_of_work, MISSING_USER_ID)


# ---------------------------------------------------------------------------
# create_staff
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestCreateStaff:
    async def test_creates_the_user_and_the_staff_record_together(self, staff_service, unit_of_work, persisted,
                                                                  save_spy):
        response = await staff_service.create_staff(unit_of_work, _create_request())

        staff = await persisted.get(Staff, response.staff_id)
        user = await persisted.get(User, response.user_id)
        assert isinstance(response, UserResponse)
        assert (staff.UserId, staff.Position) == (user.Id, "Manager")
        assert (user.Email, user.RoleId, user.Active) == ("example5@example.com", AppConstants.StaffRoleId, True)
        assert (response.role_id, response.role_name, response.position, response.active) == \
            (AppConstants.StaffRoleId, "Staff", "Manager", True)
        assert response.customer_id is None and response.created_at is not None
        save_spy.assert_awaited_once()  # one transaction for both rows

    async def test_email_in_use_creates_nothing(self, staff_service, unit_of_work, persisted, save_spy):
        before = await _staff_and_user_counts(persisted)

        with pytest.raises(ConflictError):
            await staff_service.create_staff(unit_of_work, _create_request(email="example4@example.com"))

        assert await _staff_and_user_counts(persisted) == before
        save_spy.assert_not_awaited()

    async def test_failed_save_leaves_no_user_without_a_staff_record(self, staff_service, unit_of_work, persisted,
                                                                     failing_trigger):
        await failing_trigger("BEFORE INSERT ON Staff")
        before = await _staff_and_user_counts(persisted)

        with pytest.raises(PersistenceError):
            await staff_service.create_staff(unit_of_work, _create_request())

        assert await _staff_and_user_counts(persisted) == before
        assert await persisted.count(User, User.Email == "example5@example.com") == 0

    async def test_email_taken_between_the_check_and_the_save_is_a_conflict(self, staff_service, unit_of_work,
                                                                            persisted, monkeypatch):
        monkeypatch.setattr(unit_of_work.users, "exists_async", AsyncMock(return_value=False))
        before = await _staff_and_user_counts(persisted)

        with pytest.raises(ConflictError, match="already in use"):
            await staff_service.create_staff(unit_of_work, _create_request(email="example1@example.com"))

        assert await _staff_and_user_counts(persisted) == before


# ---------------------------------------------------------------------------
# get_all_staff / get_staff_by_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetStaff:
    async def test_get_all_staff_returns_every_staff_member_sorted_by_name(self, staff_service, unit_of_work, bank):
        await staff_service.create_staff(unit_of_work, _create_request(email="example12@example.com", last_name="Abbott"))
        await staff_service.create_staff(unit_of_work, _create_request(email="example13@example.com", last_name="Zuse"))

        staff = await staff_service.get_all_staff(unit_of_work)

        assert [member.last_name for member in staff] == ["Abbott", "Mensah", "Zuse"]
        dee = staff[1]
        assert (dee.user_id, dee.position, dee.role_name, dee.email) == (bank.user_ids["Dee"], "Teller", "Staff",
                                                                          "example4@example.com")

    async def test_get_all_staff_sorts_through_one_join_and_loads_users_separately(self, staff_service,
                                                                                    unit_of_work, sql_statements):
        await staff_service.get_all_staff(unit_of_work)

        selects = [statement for statement in sql_statements if statement.startswith("SELECT")]
        list_query, users_query = selects
        assert list_query.count("JOIN") == 1 and "JOIN Users ON" in list_query
        assert "ORDER BY Users.LastName, Users.FirstName" in list_query
        assert users_query.startswith("SELECT Users.Id") and "WHERE Users.Id IN (" in users_query

    async def test_get_staff_by_id(self, staff_service, unit_of_work, bank):
        response = await staff_service.get_staff_by_id(unit_of_work, bank.user_ids["Dee"])

        assert (response.first_name, response.last_name, response.position, response.role_name) == \
            ("Dee", "Mensah", "Teller", "Staff")
        assert response.staff_id is not None

    @pytest.mark.parametrize("user", ["customer", "missing"])
    async def test_user_who_is_not_staff_is_not_found(self, staff_service, unit_of_work, bank, user):
        user_id = bank.user_ids["Ada"] if user == "customer" else MISSING_USER_ID

        with pytest.raises(NotFoundError):
            await staff_service.get_staff_by_id(unit_of_work, user_id)


# ---------------------------------------------------------------------------
# toggle_staff_active_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestToggleStaffActiveStatus:
    async def test_toggles_the_staff_members_user(self, staff_service, unit_of_work, persisted, bank):
        assert await staff_service.toggle_staff_active_status(unit_of_work, bank.user_ids["Dee"]) is False

        assert (await persisted.get(User, bank.user_ids["Dee"])).Active is False

    async def test_customer_is_not_toggled_as_staff(self, staff_service, unit_of_work, persisted, bank, save_spy):
        with pytest.raises(NotFoundError):
            await staff_service.toggle_staff_active_status(unit_of_work, bank.user_ids["Ada"])

        assert (await persisted.get(User, bank.user_ids["Ada"])).Active is True
        save_spy.assert_not_awaited()


# ---------------------------------------------------------------------------
# update_staff
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestUpdateStaff:
    async def test_updates_the_position_and_the_user_together(self, staff_service, unit_of_work, persisted, bank,
                                                              save_spy):
        response = await staff_service.update_staff(unit_of_work, bank.user_ids["Dee"], _update_request())

        staff = (await persisted.all(select(Staff).where(Staff.UserId == bank.user_ids["Dee"])))[0]
        user = await persisted.get(User, bank.user_ids["Dee"])
        assert staff.Position == "Head Teller"
        assert (user.LastName, user.Email) == ("Mensah-Ofori", "example7@example.com")
        assert (response.position, response.last_name, response.role_name) == ("Head Teller", "Mensah-Ofori",
                                                                                "Staff")
        save_spy.assert_awaited_once()

    async def test_email_of_another_user_changes_nothing(self, staff_service, unit_of_work, persisted, bank):
        with pytest.raises(ConflictError):
            await staff_service.update_staff(unit_of_work, bank.user_ids["Dee"],
                                             _update_request(email="example1@example.com"))

        staff = (await persisted.all(select(Staff).where(Staff.UserId == bank.user_ids["Dee"])))[0]
        assert staff.Position == "Teller"
        assert (await persisted.get(User, bank.user_ids["Dee"])).LastName == "Mensah"

    async def test_failed_save_changes_neither_row(self, staff_service, unit_of_work, persisted, bank,
                                                   failing_trigger):
        await failing_trigger("BEFORE UPDATE ON Staff")

        with pytest.raises(PersistenceError):
            await staff_service.update_staff(unit_of_work, bank.user_ids["Dee"], _update_request())

        assert (await persisted.get(User, bank.user_ids["Dee"])).LastName == "Mensah"

    async def test_missing_staff_is_not_found(self, staff_service, unit_of_work, bank):
        with pytest.raises(NotFoundError):
            await staff_service.update_staff(unit_of_work, bank.user_ids["Ben"], _update_request())


# ---------------------------------------------------------------------------
# delete_staff
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDeleteStaff:
    async def test_deletes_the_staff_record_and_its_user(self, staff_service, unit_of_work, persisted, save_spy):
        created = await staff_service.create_staff(unit_of_work, _create_request())
        save_spy.reset_mock()

        await staff_service.delete_staff(unit_of_work, created.user_id)

        assert await persisted.get(Staff, created.staff_id) is None
        assert await persisted.get(User, created.user_id) is None
        save_spy.assert_awaited_once()

    async def test_staff_member_with_accounts_is_restricted(self, staff_service, unit_of_work, persisted, bank):
        before = await _staff_and_user_counts(persisted)

        with pytest.raises(DeleteRestrictedError, match="has accounts"):
            await staff_service.delete_staff(unit_of_work, bank.user_ids["Dee"])

        assert await _staff_and_user_counts(persisted) == before

    async def test_staff_member_who_is_also_a_customer_is_restricted(self, staff_service, unit_of_work, persisted):
        created = await staff_service.create_staff(unit_of_work, _create_request())
        await unit_of_work.customers.add_single_async(Customer(UserId=created.user_id, Address="2 Side Street"))

        with pytest.raises(DeleteRestrictedError, match="also a customer"):
            await staff_service.delete_staff(unit_of_work, created.user_id)

        assert await persisted.get(Staff, created.staff_id) is not None

    @pytest.mark.parametrize("user", ["customer", "missing"])
    async def test_user_who_is_not_staff_is_not_found(self, staff_service, unit_of_work, bank, user):
        user_id = bank.user_ids["Ada"] if user == "customer" else MISSING_USER_ID

        with pytest.raises(NotFoundError):
            await staff_service.delete_staff(unit_of_work, user_id)
