import asyncio
from Application.AccountTypesApplication import AccountTypesApplication


async def main():
    applicationTypes = AccountTypesApplication()
    await applicationTypes.run_application()


asyncio.run(main())
