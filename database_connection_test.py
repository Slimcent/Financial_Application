import asyncio
from database_connection import DatabaseConnection


async def test_database_connection():
    """Test the database connection asynchronously."""
    db_connection = DatabaseConnection()

    connection_pool = await db_connection.connect()

    if connection_pool:
        print("Database connected successfully.")
    else:
        print("Failed to connect to the database.")

    await db_connection.close()


if __name__ == "__main__":
    asyncio.run(test_database_connection())

# Testing connection inside the terminal
# python database_connection_test.py
