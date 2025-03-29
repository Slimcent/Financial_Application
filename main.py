import asyncio
from Application.AccountTypesApplication import AccountTypesApplication
from Application.StaffApplication import StaffApplication


async def main():
    # accountType = AccountTypesApplication()
    # await accountType.run_application()

    staff = StaffApplication()
    await staff.run_application()

if __name__ == "__main__":
    asyncio.run(main())
