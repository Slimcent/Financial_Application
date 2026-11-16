import uuid
from collections.abc import Sequence

from sqlalchemy.orm import selectinload

from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Infrastructure.Logging.logger import logger
from Models.Constants.AppConstants import AppConstants
from Models.Dtos.Request.StaffCreateRequest import StaffCreateRequest
from Models.Dtos.Request.StaffUpdateRequest import StaffUpdateRequest
from Models.Dtos.Request.UpdateUserRequest import UpdateUserRequest
from Models.Dtos.Request.UserRequest import UserRequest
from Models.Dtos.Response.UserResponse import UserResponse
from Models.Entities import Staff, User
from Services.Exceptions.domain_exceptions import DeleteRestrictedError, NotFoundError
from Services.Extensions.exception_handler import EMAIL_IN_USE_MESSAGE as EMAIL_IN_USE, save_changes_async
from Services.Extensions.response_mappers import to_staff_response, to_user_response
from Services.Interfaces.i_staff_service import IStaffService
from Services.Interfaces.i_user_service import IUserService

# What the staff responses read: the staff member's user and the user's role.
STAFF_INCLUDES = ("User.Role",)

# The same objects for a list of staff that is sorted through a join on Users: the users and their roles are loaded
# by a separate query (SELECT ... IN), so Users is not joined a second time for loading.
STAFF_LIST_INCLUDES = (selectinload(Staff.User).joinedload(User.Role),)


class StaffService(IStaffService):
    def __init__(self, user_service: IUserService):
        self.user_service = user_service
        self.constants = AppConstants

    async def create_staff(self, unit_of_work: IUnitOfWork, request: StaffCreateRequest) -> UserResponse:
        user_request = UserRequest(
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            password=request.password,
            role_id=self.constants.StaffRoleId,
        )

        # The user and the staff record are saved together: either both exist afterwards or neither does.
        user, role = await self.user_service.stage_new_user(unit_of_work, user_request)
        staff = unit_of_work.staff.add_single(Staff(User=user, Position=request.position))
        await save_changes_async(unit_of_work, conflict=EMAIL_IN_USE)

        logger.info(f"Created staff {staff.Id} for user {user.Id}")
        return to_user_response(user, role, staff=staff)

    async def get_all_staff(self, unit_of_work: IUnitOfWork) -> list[UserResponse]:
        # Joined for sorting only; the related objects come from STAFF_LIST_INCLUDES.
        statement = unit_of_work.staff.query().join(Staff.User).order_by(User.LastName, User.FirstName)
        staff_members = await unit_of_work.staff.get_range_async(statement, includes=STAFF_LIST_INCLUDES)

        logger.info(f"Retrieved {len(staff_members)} staff.")
        return [to_staff_response(staff) for staff in staff_members]

    async def get_staff_by_id(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> UserResponse:
        return to_staff_response(await self._get_staff(unit_of_work, user_id, STAFF_INCLUDES))

    async def toggle_staff_active_status(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> bool:
        if not await unit_of_work.staff.exists_async(Staff.UserId == user_id):
            raise NotFoundError(f"Staff with User Id {user_id} does not exist.")

        return await self.user_service.toggle_user_active_status(unit_of_work, user_id)

    async def update_staff(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID,
                           request: StaffUpdateRequest) -> UserResponse:
        user_update_request = UpdateUserRequest(
            last_name=request.last_name,
            first_name=request.first_name,
            email=request.email,
        )

        staff = await self._get_staff(unit_of_work, user_id, STAFF_INCLUDES)

        # The position and the user details are saved together.
        await self.user_service.stage_user_update(unit_of_work, staff.User, user_update_request)
        unit_of_work.staff.update_single(staff, {"Position": request.position})
        await save_changes_async(unit_of_work, conflict=EMAIL_IN_USE)

        logger.info(f"Updated staff with User Id {user_id}")
        return to_staff_response(staff)

    async def delete_staff(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> None:
        staff = await self._get_staff(unit_of_work, user_id, ("User.customer",))

        if staff.User.customer is not None:
            raise DeleteRestrictedError(f"User {user_id} is also a customer and cannot be deleted as staff.")
        await self.user_service.ensure_user_can_be_deleted(unit_of_work, user_id)

        # The staff record and its user are deleted together (the staff row first).
        unit_of_work.staff.delete_single(staff)
        unit_of_work.users.delete_single(staff.User)
        await save_changes_async(unit_of_work,
                                 restricted=f"Staff with User Id {user_id} is still referenced by other records.")

        logger.info(f"Deleted staff with User Id {user_id}")

    @staticmethod
    async def _get_staff(unit_of_work: IUnitOfWork, user_id: uuid.UUID, includes: Sequence[str]) -> Staff:
        staff = await unit_of_work.staff.get_single_async(Staff.UserId == user_id, includes=includes)
        if staff is None:
            raise NotFoundError(f"Staff with User Id {user_id} does not exist.")
        return staff
