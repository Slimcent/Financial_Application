import uuid

from sqlalchemy import or_

from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Infrastructure.Logging.logger import logger
from Infrastructure.Security import hash_password_async
from Models.Dtos.Request.UpdateUserRequest import UpdateUserRequest
from Models.Dtos.Request.UserRequest import UserRequest
from Models.Dtos.Response.UserResponse import UserResponse
from Models.Entities import Account, Role, Transaction, User
from Services.Exceptions.domain_exceptions import ConflictError, DeleteRestrictedError, NotFoundError
from Services.Extensions.exception_handler import EMAIL_IN_USE_MESSAGE as EMAIL_IN_USE, save_changes_async
from Services.Extensions.response_mappers import to_user_response
from Services.Interfaces.i_user_service import IUserService


class UserService(IUserService):

    async def create_user(self, unit_of_work: IUnitOfWork, request: UserRequest) -> uuid.UUID:
        user, _ = await self.stage_new_user(unit_of_work, request)
        await save_changes_async(unit_of_work, conflict=EMAIL_IN_USE)

        logger.info(f"Created user {user.Id}")
        return user.Id

    async def stage_new_user(self, unit_of_work: IUnitOfWork, request: UserRequest) -> tuple[User, Role]:
        role = await unit_of_work.roles.get_by_id_async(request.role_id)
        if role is None:
            raise NotFoundError(f"Role with Id {request.role_id} does not exist.")

        if await unit_of_work.users.exists_async(User.Email == request.email):
            raise ConflictError(EMAIL_IN_USE)

        user = unit_of_work.users.add_single(User(
            LastName=request.last_name,
            FirstName=request.first_name,
            Email=request.email,
            RoleId=role.Id,
            Password=await hash_password_async(request.password),
        ))
        return user, role

    async def toggle_user_active_status(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> bool:
        # Locked, so two toggles of the same user at the same time cannot both read the old status.
        user = await unit_of_work.users.get_by_id_async(user_id, for_update=True)
        if user is None:
            raise NotFoundError(f"User with Id {user_id} does not exist.")

        new_status = not user.Active
        unit_of_work.users.update_single(user, {"Active": new_status})
        await save_changes_async(unit_of_work, failed=f"The status of user {user_id} could not be changed.")

        logger.info(f"User {user_id} active status changed to {new_status}.")
        return new_status

    async def update_user(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID,
                          request: UpdateUserRequest) -> UserResponse:
        user = await unit_of_work.users.get_by_id_async(user_id, includes=["Role"])
        if user is None:
            raise NotFoundError(f"User with Id {user_id} does not exist.")

        await self.stage_user_update(unit_of_work, user, request)
        await save_changes_async(unit_of_work, conflict=EMAIL_IN_USE)

        logger.info(f"Updated user {user_id}")
        return to_user_response(user, user.Role)

    async def stage_user_update(self, unit_of_work: IUnitOfWork, user: User, request: UpdateUserRequest) -> User:
        if await unit_of_work.users.exists_async(User.Email == request.email, User.Id != user.Id):
            raise ConflictError(EMAIL_IN_USE)

        return unit_of_work.users.update_single(user, {
            "LastName": request.last_name,
            "FirstName": request.first_name,
            "Email": request.email,
        })

    async def delete_user(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> None:
        user = await unit_of_work.users.get_by_id_async(user_id, includes=["Staff", "customer"])
        if user is None:
            raise NotFoundError(f"User with Id {user_id} does not exist.")

        if user.Staff is not None or user.customer is not None:
            raise DeleteRestrictedError(f"User {user_id} has a staff or customer record; delete the staff member or "
                                        f"the customer instead.")
        await self.ensure_user_can_be_deleted(unit_of_work, user_id)

        unit_of_work.users.delete_single(user)
        await save_changes_async(unit_of_work, restricted=f"User {user_id} is still referenced by other records.")
        logger.info(f"Deleted user {user_id}")

    async def ensure_user_can_be_deleted(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> None:
        if await unit_of_work.accounts.exists_async(Account.UserId == user_id):
            raise DeleteRestrictedError(f"User {user_id} has accounts and cannot be deleted.")

        if await unit_of_work.transactions.exists_async(or_(Transaction.UserId == user_id,
                                                            Transaction.SenderId == user_id)):
            raise DeleteRestrictedError(f"User {user_id} has transactions and cannot be deleted.")
