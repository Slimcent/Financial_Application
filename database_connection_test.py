import asyncio
from database_connection import DatabaseConnection


async def test_database_connection():
    """Test the database connection asynchronously."""
    # Initialize the database connection object
    db_connection = DatabaseConnection()

    # Connect to the database
    connection_pool = await db_connection.connect()

    if connection_pool:
        print("Database connected successfully.")
    else:
        print("Failed to connect to the database.")

    # Close the connection pool
    await db_connection.close()


# If this module is executed directly, run the test.
if __name__ == "__main__":
    asyncio.run(test_database_connection())

# To test this connection, type this inside the terminal
# python database_connection_test.py
