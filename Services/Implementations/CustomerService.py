import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Infrastructure.Logging.logger import logger
from Models.Constants.AppConstants import AppConstants
from Models.Dtos.Request.CustomerRequest import CustomerRequest
from Models.Dtos.Request.CustomerUpdateRequest import CustomerUpdateRequest
from Models.Dtos.Request.UpdateUserRequest import UpdateUserRequest
from Models.Dtos.Request.UserRequest import UserRequest
from Models.Dtos.Request.base_request import AccountNumber
from Models.Dtos.Response.AccountsResponse import AccountsResponse
from Models.Dtos.Response.UserResponse import UserResponse
from Models.Entities import Account, AccountType, Customer, Transaction, User
from Services.Exceptions.domain_exceptions import (BusinessRuleError, ConflictError, DeleteRestrictedError,
                                                   NotFoundError)
from Services.Extensions.exception_handler import (EMAIL_IN_USE_MESSAGE, integrity_constraint_name,
                                                   save_changes_async, validated)
from Services.Extensions.response_mappers import to_accounts_response, to_customer_response, to_user_response
from Services.Handler.AccountNumber import generate_account_number
from Services.Interfaces.i_customer_service import ICustomerService
from Services.Interfaces.i_user_service import IUserService

# What the customer responses read: the customer's user, its role, and its accounts with their account types.
CUSTOMER_INCLUDES = ("user.Role", "user.accounts.account_type")

# The same objects for a list of customers that is sorted through a join on Users: the users, roles and accounts are
# loaded by separate queries (SELECT ... IN), so Users is not joined a second time for loading.
CUSTOMER_LIST_INCLUDES = (
    selectinload(Customer.user).options(joinedload(User.Role),
                                        selectinload(User.accounts).joinedload(Account.account_type)),
)

# Generated account numbers tried before giving up (a collision is already unlikely: 10^8 numbers per type).
MAX_ACCOUNT_NUMBER_ATTEMPTS = 10

# Saves tried when the generated account number was taken by another operation between the check and the save.
MAX_SAVE_ATTEMPTS = 3

OPENING_BALANCE = Decimal("0.00")

# Unique constraints the customer operations can violate (names from NAMING_CONVENTION, see the migrations).
EMAIL_CONSTRAINT = "uq_Users_Email"
ACCOUNT_NUMBER_CONSTRAINT = "uq_Accounts_AccountNumber"
ACCOUNT_PER_TYPE_CONSTRAINT = "uq_Accounts_UserId_AccountTypeId"
CUSTOMER_PER_USER_CONSTRAINT = "uq_Customers_UserId"

CONFLICT_MESSAGES = {
    EMAIL_CONSTRAINT: EMAIL_IN_USE_MESSAGE,
    ACCOUNT_NUMBER_CONSTRAINT: "No free account number could be assigned; please try again.",
    ACCOUNT_PER_TYPE_CONSTRAINT: "The customer already has an account of this account type.",
    CUSTOMER_PER_USER_CONSTRAINT: "The user is already a customer.",
}
CUSTOMER_CONFLICT_MESSAGE = "The customer data conflicts with existing data."


class CustomerService(ICustomerService):
    def __init__(self, user_service: IUserService):
        self.user_service = user_service
        self.constants = AppConstants

    async def create_customer(self, unit_of_work: IUnitOfWork, request: CustomerRequest) -> UserResponse:
        user_request = UserRequest(
            last_name=request.last_name,
            first_name=request.first_name,
            email=request.email,
            password=request.password,
            role_id=self.constants.CustomerRoleId,
        )

        account_type = await self._get_account_type(unit_of_work, request.account_type_id)

        # The user, the customer record and the first account are saved together: all of them or none. A failed
        # save discards what was staged, so each attempt stages new objects.
        for attempt in range(1, MAX_SAVE_ATTEMPTS + 1):
            user, role = await self.user_service.stage_new_user(unit_of_work, user_request)
            customer = unit_of_work.customers.add_single(Customer(user=user, Address=request.address))
            account_number = await self._new_account_number_async(unit_of_work, account_type.Id)
            account = unit_of_work.accounts.add_single(Account(user=user, AccountTypeId=account_type.Id,
                                                               AccountNumber=account_number,
                                                               Balance=OPENING_BALANCE))
            if await self._save_retrying_account_number_async(unit_of_work, attempt):
                break

        logger.info(f"Created customer {customer.Id} and account {account.Id} for user {user.Id}")
        return to_user_response(user, role, customer=customer, accounts=[to_accounts_response(account, account_type)])

    async def update_customer(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID,
                              request: CustomerUpdateRequest) -> UserResponse:
        user_update_request = UpdateUserRequest(
            last_name=request.last_name,
            first_name=request.first_name,
            email=request.email,
        )

        customer = await self._get_customer(unit_of_work, user_id, CUSTOMER_INCLUDES)

        # The address and the user details are saved together.
        await self.user_service.stage_user_update(unit_of_work, customer.user, user_update_request)
        unit_of_work.customers.update_single(customer, {"Address": request.address})
        await self._save_async(unit_of_work)

        logger.info(f"Updated customer with User Id {user_id}")
        return to_customer_response(customer)

    async def delete_customer(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> None:
        customer = await self._get_customer(unit_of_work, user_id, ("user.Staff",))

        if customer.user.Staff is not None:
            raise DeleteRestrictedError(f"User {user_id} is also a staff member and cannot be deleted as a customer.")
        await self.user_service.ensure_user_can_be_deleted(unit_of_work, user_id)

        # The customer record and its user are deleted together (the customer row first).
        unit_of_work.customers.delete_single(customer)
        unit_of_work.users.delete_single(customer.user)
        await save_changes_async(unit_of_work,
                                 restricted=f"Customer with User Id {user_id} is still referenced by other records.")

        logger.info(f"Deleted customer with User Id {user_id}")

    async def deactivate_customer_account(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> UserResponse:
        customer = await self._get_customer(unit_of_work, user_id, CUSTOMER_INCLUDES)

        # The customer's user and every account of the customer that is still active are deactivated together, in
        # one transaction. The accounts are selected when the unit of work saves, so an account opened after the
        # customer was loaded is deactivated too.
        if customer.user.Active:
            unit_of_work.users.update_single(customer.user, {"Active": False})
        unit_of_work.accounts.update_range(Account.UserId == user_id, Account.Active.is_(True),
                                           values={"Active": False})
        await self._save_async(unit_of_work)

        logger.info(f"Deactivated customer with User Id {user_id} and the customer's accounts")
        return to_customer_response(customer)

    async def get_all_customers(self, unit_of_work: IUnitOfWork) -> list[UserResponse]:
        # Joined for sorting only; the related objects come from CUSTOMER_LIST_INCLUDES.
        statement = unit_of_work.customers.query().join(Customer.user).order_by(User.LastName, User.FirstName)
        customers = await unit_of_work.customers.get_range_async(statement, includes=CUSTOMER_LIST_INCLUDES)

        logger.info(f"Retrieved {len(customers)} customers.")
        return [to_customer_response(customer) for customer in customers]

    async def get_customer_by_id(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID) -> UserResponse:
        return to_customer_response(await self._get_customer(unit_of_work, user_id, CUSTOMER_INCLUDES))

    async def open_account(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID,
                           account_type_id: int) -> AccountsResponse:
        customer = await self._get_customer(unit_of_work, user_id, ("user",))
        if not customer.user.Active:
            raise BusinessRuleError(f"Customer {user_id} is deactivated; no account can be opened.")
        account_type = await self._get_account_type(unit_of_work, account_type_id)

        if await unit_of_work.accounts.exists_async(Account.UserId == user_id, Account.AccountTypeId == account_type_id):
            raise ConflictError(f"Customer {user_id} already has a {account_type.Type} account.")

        for attempt in range(1, MAX_SAVE_ATTEMPTS + 1):
            account_number = await self._new_account_number_async(unit_of_work, account_type_id)
            account = unit_of_work.accounts.add_single(Account(UserId=user_id, AccountTypeId=account_type_id,
                                                               AccountNumber=account_number,
                                                               Balance=OPENING_BALANCE))
            if await self._save_retrying_account_number_async(unit_of_work, attempt):
                break

        logger.info(f"Opened {account_type.Type} account {account.Id} for customer {user_id}")
        return to_accounts_response(account, account_type)

    async def close_account(self, unit_of_work: IUnitOfWork, user_id: uuid.UUID, account_number: str) -> None:
        account_number = validated(AccountNumber, account_number, "account number")
        await self._get_customer(unit_of_work, user_id, ())

        # Locked, so the balance cannot change between the check and the deletion.
        account = await unit_of_work.accounts.get_single_async(Account.AccountNumber == account_number,
                                                               Account.UserId == user_id, for_update=True)
        if account is None:
            raise NotFoundError(f"Customer {user_id} has no account with this account number.")

        if account.Balance != 0:
            raise BusinessRuleError("The account still holds a balance; transfer it before closing the account.")
        if await unit_of_work.transactions.exists_async(Transaction.AccountId == account.Id):
            raise DeleteRestrictedError("The account has transactions and cannot be closed.")

        unit_of_work.accounts.delete_single(account)
        await save_changes_async(unit_of_work, restricted="The account is still referenced by other records.")

        logger.info(f"Closed account {account.Id} of customer {user_id}")

    @staticmethod
    async def _get_customer(unit_of_work: IUnitOfWork, user_id: uuid.UUID, includes: Sequence[str]) -> Customer:
        customer = await unit_of_work.customers.get_single_async(Customer.UserId == user_id, includes=includes)
        if customer is None:
            raise NotFoundError(f"Customer with User Id {user_id} does not exist.")
        return customer

    @staticmethod
    async def _get_account_type(unit_of_work: IUnitOfWork, account_type_id: int) -> AccountType:
        account_type = await unit_of_work.account_types.get_by_id_async(account_type_id)
        if account_type is None:
            raise NotFoundError(f"Account type with Id {account_type_id} does not exist.")
        return account_type

    @staticmethod
    async def _new_account_number_async(unit_of_work: IUnitOfWork, account_type_id: int) -> str:
        """A generated account number that no account uses yet. (Another operation can still take it before this
        one saves; the save then fails on the unique constraint and is retried with a new number.)"""
        for _ in range(MAX_ACCOUNT_NUMBER_ATTEMPTS):
            account_number = generate_account_number(account_type_id)
            if not await unit_of_work.accounts.exists_async(Account.AccountNumber == account_number):
                return account_number
        raise ConflictError(CONFLICT_MESSAGES[ACCOUNT_NUMBER_CONSTRAINT])

    @staticmethod
    async def _save_retrying_account_number_async(unit_of_work: IUnitOfWork, attempt: int) -> bool:
        """Save what is staged. True when saved; False when the generated account number was taken by another
        operation meanwhile and another attempt is left: the unit of work has discarded the staged changes, and
        the caller stages them again with a new account number. Any other violation raises the matching domain error
        (a ConflictError with the message of the unique constraint the database reported, see CONFLICT_MESSAGES)."""
        try:
            await CustomerService._save_async(unit_of_work)
            return True
        except ConflictError as error:
            violation = error.__cause__
            taken = (isinstance(violation, IntegrityError)
                     and integrity_constraint_name(violation) == ACCOUNT_NUMBER_CONSTRAINT)
            if taken and attempt < MAX_SAVE_ATTEMPTS:
                logger.warning(f"Account number taken while saving (attempt {attempt} of {MAX_SAVE_ATTEMPTS}); "
                               f"retrying with a new account number.")
                return False
            raise

    @staticmethod
    async def _save_async(unit_of_work: IUnitOfWork) -> None:
        """Save what is staged; a violation raises the matching domain error (see save_changes_async), a unique
        violation with the message of its constraint (CONFLICT_MESSAGES)."""
        await save_changes_async(unit_of_work, conflict=CUSTOMER_CONFLICT_MESSAGE, conflicts=CONFLICT_MESSAGES)
