# import asyncio
# from sqlalchemy import text
# import sys
# from database_orm_async import engine
#
# print(sys.path)
#
#
# async def test_connection():
#     try:
#         async with engine.connect() as connection:
#             print("Successfully connected to the database!")
#
#             result = await connection.execute(text("SELECT DATABASE();"))
#             db_name = result.scalar()
#
#             print(f"Connected to database: {db_name}")
#     except Exception as e:
#         print(f"Failed to connect to the database: {e}")
#     finally:
#         await engine.dispose()
#
#
# if __name__ == "__main__":
#     asyncio.run(test_connection())


import asyncio
from sqlalchemy import text
import sys
from database_orm_async import Database

print(sys.path)


async def test_connection():
    db = Database()
    try:
        async with db.engine.connect() as connection:
            print("Successfully connected to the database!")

            result = await connection.execute(text("SELECT DATABASE();"))
            db_name = result.scalar()

            print(f"📂 Connected to database: {db_name}")
    except Exception as e:
        print(f"Failed to connect to the database: {e}")
    finally:
        await db.dispose()


if __name__ == "__main__":
    asyncio.run(test_connection())

# To test
# python database_orm_connection_test_async.py
