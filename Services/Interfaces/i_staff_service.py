"""Contract of the staff service: staff members (a user with the staff role and a staff record).

Every method is given the caller's unit of work, which must be active (``async with``). Methods that change data
save their changes through it before they return: each is one transaction, so a staff member and its user are
always created, updated or deleted together. Errors are raised as the domain errors in Services/Exceptions.
"""
import uuid
from abc import ABC, abstractmethod

from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Models.Dtos.Request.StaffCreateRequest import StaffCreateRequest
from Models.Dtos.Request.StaffUpdateRequest import StaffUpdateRequest
from Models.Dtos.Response.UserResponse import UserResponse


class IStaffService(ABC):

    @abstractmethod
    async def create_staff(self, unit_of_work: IUnitOfWork, request: StaffCreateRequest) -> UserResponse:
        """Create the user and its staff record; returns the new staff member.

        Raises NotFoundError if the staff role is not seeded, ConflictError if the email address is in use.
        """

    @abstractmethod
    async def get_all_staff(self, unit_of_work: IUnitOfWork) -> list[UserResponse]:
        """Every staff member, ordered by last and first name."""

    @abstractmethod
    async def get_staff_by_id(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> UserResponse:
        """The staff member with this user Id. Raises NotFoundError."""

    @abstractmethod
    async def toggle_staff_active_status(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> bool:
        """Activate or deactivate a staff member's user; returns the new status. Raises NotFoundError."""

    @abstractmethod
    async def update_staff(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID,
                           request: StaffUpdateRequest) -> UserResponse:
        """Update the position and the user details together; returns the updated staff member.

        Raises NotFoundError, or ConflictError if the email address belongs to another user.
        """

    @abstractmethod
    async def delete_staff(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> None:
        """Delete the staff record and its user together.

        Raises NotFoundError, or DeleteRestrictedError if the user has accounts or transactions or is also a
        customer.
        """
