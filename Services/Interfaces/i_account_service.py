"""Contract of the account service: reading accounts and balances.

Every method is given the caller's unit of work, which must be active (``async with``). Balances are Decimals.
Errors are raised as the domain errors in Services/Exceptions.
"""
import uuid
from abc import ABC, abstractmethod

from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Models.Dtos.Response.AccountResponse import AccountResponse
from Models.Dtos.Response.AccountsResponse import AccountsResponse


class IAccountService(ABC):

    @abstractmethod
    async def get_all_customer_accounts(self, unit_of_work: IUnitOfWork) -> list[AccountResponse]:
        """Every customer with its accounts and their total balance, ordered by last and first name."""

    @abstractmethod
    async def get_customer_account_details(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID,
                                           account_type_id: int) -> AccountResponse:
        """A user's account of one account type, with the owner's details. Raises NotFoundError."""

    @abstractmethod
    async def get_customer_accounts_with_user_id(self, unit_of_work: IUnitOfWork,
                                                 user_id: uuid.UUID) -> AccountResponse:
        """Every account of a user and their total balance. Raises NotFoundError if the user does not exist."""

    @abstractmethod
    async def get_account_details_by_account_number(self, unit_of_work: IUnitOfWork,
                                                    account_number: str) -> AccountsResponse:
        """The account with this account number. Raises InvalidInputError or NotFoundError."""
