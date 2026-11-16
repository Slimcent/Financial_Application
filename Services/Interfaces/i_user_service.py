"""Contract of the user service: the user records shared by staff and customers.

Every method is given the caller's unit of work, which must be active (``async with``). Methods that change data
save their changes through it before they return (one transaction per call). The ``stage_*`` and ``ensure_*``
methods are building blocks for other services: they only check and stage, and the calling service saves.

Errors are raised as the domain errors in Services/Exceptions; the unit of work then rolls back.
"""
import uuid
from abc import ABC, abstractmethod

from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Models.Dtos.Request.UpdateUserRequest import UpdateUserRequest
from Models.Dtos.Request.UserRequest import UserRequest
from Models.Dtos.Response.UserResponse import UserResponse
from Models.Entities import Role, User


class IUserService(ABC):

    @abstractmethod
    async def create_user(self, unit_of_work: IUnitOfWork, request: UserRequest) -> uuid.UUID:
        """Create a user and return its Id.

        Raises NotFoundError if the role does not exist, ConflictError if the email address is in use.
        """

    @abstractmethod
    async def stage_new_user(self, unit_of_work: IUnitOfWork, request: UserRequest) -> tuple[User, Role]:
        """Check and stage a new user (password hashed) without saving; returns the user and its role.

        The user's Id is known once the calling service has saved. Raises NotFoundError if the role does not
        exist, ConflictError if the email address is in use.
        """

    @abstractmethod
    async def toggle_user_active_status(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> bool:
        """Activate an inactive user or deactivate an active one; returns the new status.

        Raises NotFoundError if the user does not exist.
        """

    @abstractmethod
    async def update_user(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID,
                          request: UpdateUserRequest) -> UserResponse:
        """Update a user's names and email address; returns the updated user.

        Raises NotFoundError if the user does not exist, ConflictError if the email address belongs to another
        user.
        """

    @abstractmethod
    async def stage_user_update(self, unit_of_work: IUnitOfWork, user: User, request: UpdateUserRequest) -> User:
        """Check and stage the update of a user loaded through ``unit_of_work``, without saving.

        Raises ConflictError if the email address belongs to another user.
        """

    @abstractmethod
    async def delete_user(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> None:
        """Delete a user that has no staff or customer record, no accounts and no transactions.

        Raises NotFoundError if the user does not exist, DeleteRestrictedError if it still has a staff or customer
        record (delete it through the staff or customer service), accounts or transactions.
        """

    @abstractmethod
    async def ensure_user_can_be_deleted(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> None:
        """Raise DeleteRestrictedError if the user owns accounts or has transactions (as owner or sender)."""
