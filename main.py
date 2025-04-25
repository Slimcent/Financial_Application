import asyncio
from Application.AccountTypesApplication import AccountTypesApplication
from Application.CustomerApplication import CustomerApplication
from Application.StaffApplication import StaffApplication
from ApplicationProcessing.ProcessAccount import ProcessAccount
from ApplicationProcessing.ProcessTransaction import ProcessTransaction


async def main():
    # accountType = AccountTypesApplication()
    # await accountType.run_application()

    # staff = StaffApplication()
    # await staff.run_application()

    # customer = CustomerApplication()
    # await customer.run_application()

    transaction = ProcessTransaction()
    await transaction.run_application()

    # account = ProcessAccount()
    # await account.run_application()

if __name__ == "__main__":
    asyncio.run(main())
