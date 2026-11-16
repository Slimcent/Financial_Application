"""Composition root: the one place where the application's objects are created and wired together.

* The database (engine and session factory) is created once.
* The services are created once. They hold no state and no database session, so one instance of each serves every
  caller; they depend on each other through their interfaces (Services/Interfaces).
* A unit of work is created per business operation by create_unit_of_work(). The caller enters it, passes it to
  the services it calls and so decides where the operation starts and ends:

      async with container.create_unit_of_work() as unit_of_work:
          staff = await container.staff_service.get_staff_by_id(unit_of_work, user_id)

  An API can expose the same factory as a request-scoped dependency later (e.g. a FastAPI dependency that enters
  a unit of work and yields it for the request).
"""
from Data.Implementations.unit_of_work import UnitOfWork
from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Data.database_orm_async import Database
from Services.Implementations.AccountService import AccountService
from Services.Implementations.AccountTypeService import AccountTypeService
from Services.Implementations.CustomerService import CustomerService
from Services.Implementations.StaffService import StaffService
from Services.Implementations.UserService import UserService
from Services.Implementations.transaction_service import TransactionService
from Services.Interfaces.i_account_service import IAccountService
from Services.Interfaces.i_account_type_service import IAccountTypeService
from Services.Interfaces.i_customer_service import ICustomerService
from Services.Interfaces.i_staff_service import IStaffService
from Services.Interfaces.i_transaction_service import ITransactionService
from Services.Interfaces.i_user_service import IUserService


class Container:
    def __init__(self, database: Database | None = None):
        self.database = database if database is not None else Database()

        self.user_service: IUserService = UserService()
        self.staff_service: IStaffService = StaffService(self.user_service)
        self.customer_service: ICustomerService = CustomerService(self.user_service)
        self.account_type_service: IAccountTypeService = AccountTypeService()
        self.account_service: IAccountService = AccountService()
        self.transaction_service: ITransactionService = TransactionService()

    def create_unit_of_work(self) -> IUnitOfWork:
        """A new unit of work on the application's database (a UnitOfWorkFactory); enter it with ``async with``."""
        return UnitOfWork(self.database.SessionLocal)

    async def dispose(self) -> None:
        """Close the database connections. Call once, when the application stops."""
        await self.database.dispose()
