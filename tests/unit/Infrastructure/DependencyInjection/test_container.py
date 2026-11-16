"""Infrastructure/DependencyInjection/container.py: the composition root wires the services and hands out units of
work. A stand-in database is used: no engine, no connection."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from Data.Implementations.unit_of_work import UnitOfWork
from Data.Interfaces.i_unit_of_work import IUnitOfWork
from Infrastructure.DependencyInjection import container as container_module
from Infrastructure.DependencyInjection.container import Container
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

SERVICES = [
    ("user_service", IUserService, UserService),
    ("staff_service", IStaffService, StaffService),
    ("customer_service", ICustomerService, CustomerService),
    ("account_type_service", IAccountTypeService, AccountTypeService),
    ("account_service", IAccountService, AccountService),
    ("transaction_service", ITransactionService, TransactionService),
]


@pytest.fixture
def session():
    session = MagicMock()
    session.close = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def database(session):
    """Stands in for Data/database_orm_async.Database: a session factory and dispose()."""
    database = MagicMock()
    database.SessionLocal = MagicMock(return_value=session)
    database.dispose = AsyncMock()
    return database


@pytest.fixture
def container(database):
    return Container(database)


@pytest.mark.parametrize("attribute, interface, implementation", SERVICES, ids=[name for name, _, _ in SERVICES])
def test_each_service_is_provided_through_its_interface(container, attribute, interface, implementation):
    service = getattr(container, attribute)

    assert isinstance(service, interface)
    assert type(service) is implementation


@pytest.mark.parametrize("attribute", [name for name, _, _ in SERVICES])
def test_services_are_created_once(container, attribute):
    assert getattr(container, attribute) is getattr(container, attribute)


@pytest.mark.parametrize("attribute", ["staff_service", "customer_service"])
def test_user_service_is_shared_by_the_services_that_depend_on_it(container, attribute):
    assert getattr(container, attribute).user_service is container.user_service


def test_each_call_creates_a_new_inactive_unit_of_work(container):
    first, second = container.create_unit_of_work(), container.create_unit_of_work()

    assert isinstance(first, IUnitOfWork) and isinstance(first, UnitOfWork)
    assert first is not second
    assert not first.is_active and not second.is_active


@pytest.mark.asyncio
async def test_unit_of_work_uses_the_database_sessions(container, database, session):
    database.SessionLocal.assert_not_called()  # no session until a unit of work is entered

    async with container.create_unit_of_work() as unit_of_work:
        assert unit_of_work.is_active

    database.SessionLocal.assert_called_once_with()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_unit_of_work_is_a_unit_of_work_factory(container, database):
    # Callers (the Application classes, later the API) are given the bound method as their UnitOfWorkFactory.
    factory = container.create_unit_of_work

    async with factory() as first:
        pass
    async with factory() as second:
        pass

    assert first is not second
    assert database.SessionLocal.call_count == 2


@pytest.mark.asyncio
async def test_dispose_closes_the_database(container, database):
    await container.dispose()

    database.dispose.assert_awaited_once_with()


def test_application_database_is_used_by_default(monkeypatch, database):
    monkeypatch.setattr(container_module, "Database", MagicMock(return_value=database))

    assert Container().database is database
