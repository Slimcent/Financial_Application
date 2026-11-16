import asyncio
from Application.AccountApplication import AccountApplication
from Application.AccountTypesApplication import AccountTypesApplication
from Application.CustomerApplication import CustomerApplication
from Application.StaffApplication import StaffApplication
from Application.TransactionApplication import TransactionApplication
from ApplicationProcessing.ProcessAccount import ProcessAccount
from ApplicationProcessing.ProcessTransaction import ProcessTransaction
from Data.Seed.lookup_seed import LookupSeedError, seed_lookups_on_first_run_async
from Infrastructure.DependencyInjection.container import Container
from Services.Exceptions.domain_exceptions import ServiceError


async def main():
    container = Container()
    unit_of_work_factory = container.create_unit_of_work

    try:
        # The services refer to the lookup rows (roles, account types, transaction types / modes / statuses) by the
        # identifiers in AppConstants. Missing rows are added - all of them the first time the application runs
        # against a new database; later runs only check that they are there.
        async with unit_of_work_factory() as unit_of_work:
            await seed_lookups_on_first_run_async(unit_of_work)

        account_type = AccountTypesApplication(unit_of_work_factory, container.account_type_service)
        staff = StaffApplication(unit_of_work_factory, container.staff_service)
        customer = CustomerApplication(unit_of_work_factory, container.customer_service)
        account = ProcessAccount(AccountApplication(unit_of_work_factory, container.account_service))
        transaction = ProcessTransaction(TransactionApplication(unit_of_work_factory, container.account_service,
                                                                container.transaction_service))

        # await account_type.run_application()

        # await staff.run_application()

        # await customer.run_application()

        await transaction.run_application()

        # await account.run_application()

    except LookupSeedError as e:
        print(f"[Seed Error] {e}")
    except ServiceError as e:
        print(f"[Service Error] {e.message}")
    except ValueError as e:
        print(f"[App Error] {e}")
    except Exception as e:
        print(f"[Unhandled] {e}")
    finally:
        await container.dispose()


if __name__ == "__main__":
    asyncio.run(main())
