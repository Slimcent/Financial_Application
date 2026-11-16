"""Contract of the account type service.

Every method is given the caller's unit of work, which must be active (``async with``). Methods that change data
save their changes through it before they return. Errors are raised as the domain errors in Services/Exceptions.
"""
from abc import ABC, abstractmethod

from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Models.Dtos.Request.AccountTypeRequest import AccountTypeRequest
from Models.Dtos.Response.AccountTypeResponse import AccountTypeResponse


class IAccountTypeService(ABC):

    @abstractmethod
    async def get_all_account_types(self, unit_of_work: IUnitOfWork) -> list[AccountTypeResponse]:
        """Every account type, ordered by Id."""

    @abstractmethod
    async def get_account_type_by_id(self, unit_of_work: IUnitOfWork, account_type_id: int) -> AccountTypeResponse:
        """The account type with this Id. Raises NotFoundError."""

    @abstractmethod
    async def add_account_type(self, unit_of_work: IUnitOfWork, request: AccountTypeRequest) -> AccountTypeResponse:
        """Add an account type; returns it with its new Id. Raises ConflictError if the name is in use."""

    @abstractmethod
    async def update_account_type(self, unit_of_work: IUnitOfWork, account_type_id: int,
                                  request: AccountTypeRequest) -> AccountTypeResponse:
        """Rename an account type. Raises NotFoundError, or ConflictError if another type has the name."""

    @abstractmethod
    async def delete_account_type(self, unit_of_work: IUnitOfWork, account_type_id: int) -> None:
        """Delete an account type. Raises NotFoundError, or DeleteRestrictedError if accounts use it."""
