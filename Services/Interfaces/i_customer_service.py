"""Contract of the customer service: customers (a user with the customer role, a customer record and accounts).

Every method is given the caller's unit of work, which must be active (``async with``). Methods that change data
save their changes through it before they return: each is one transaction, so a customer, its user and its first
account are always created together. Errors are raised as the domain errors in Services/Exceptions.
"""
import uuid
from abc import ABC, abstractmethod

from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Models.Dtos.Request.CustomerRequest import CustomerRequest
from Models.Dtos.Request.CustomerUpdateRequest import CustomerUpdateRequest
from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Response.UserResponse import UserResponse


class ICustomerService(ABC):

    @abstractmethod
    async def create_customer(self, unit_of_work: IUnitOfWork, request: CustomerRequest) -> UserResponse:
        """Create the user, the customer record and the customer's first account; returns the new customer.

        Raises NotFoundError if the account type (or the customer role) does not exist, ConflictError if the email
        address is in use or no free account number was found.
        """

    @abstractmethod
    async def update_customer(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID,
                              request: CustomerUpdateRequest) -> UserResponse:
        """Update the address and the user details together; returns the updated customer.

        Raises NotFoundError, or ConflictError if the email address belongs to another user.
        """

    @abstractmethod
    async def delete_customer(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> None:
        """Delete the customer record and its user together.

        Raises NotFoundError, or DeleteRestrictedError if the customer has accounts or transactions or is also a
        staff member.
        """

    @abstractmethod
    async def deactivate_customer_account(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> UserResponse:
        """Deactivate the customer instead of deleting it: the customer's user (Users.Active = False) and every
        account of the customer (Accounts.Active = False), in one transaction; returns the customer. The customer
        record, the accounts with their balances and the transaction history are kept, but an inactive customer's
        accounts can neither be funded nor send or receive transfers. Deactivating an inactive customer changes
        nothing.

        Raises NotFoundError if the customer does not exist.
        """

    @abstractmethod
    async def get_all_customers(self, unit_of_work: IUnitOfWork) -> list[UserResponse]:
        """Every customer with its accounts, ordered by last and first name."""

    @abstractmethod
    async def get_customer_by_id(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> UserResponse:
        """The customer with this user Id, with its accounts. Raises NotFoundError."""

    @abstractmethod
    async def open_account(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID,
                           account_type_id: int) -> AccountsResponse:
        """Open an account of another type for a customer; returns the new account.

        Raises NotFoundError if the customer or the account type does not exist, BusinessRuleError if the customer
        is deactivated, ConflictError if the customer already has an account of that type or no free account number
        was found.
        """

    @abstractmethod
    async def close_account(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID, account_number: str) -> None:
        """Close (delete) one of the customer's accounts. Only an account with a zero balance and no transactions
        can be closed; once its last account is closed, the customer itself can be deleted.

        Raises InvalidInputError for an invalid account number, NotFoundError if the customer or the account does
        not exist, BusinessRuleError if the balance is not zero, DeleteRestrictedError if the account has
        transactions.
        """
