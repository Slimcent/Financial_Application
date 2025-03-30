import aiomysql
from dotenv import load_dotenv
import os

load_dotenv()


class DatabaseConnection:
    def __init__(self):
        self.pool = None
        self.host = os.getenv("DB_HOST")
        self.database = os.getenv("DB_NAME")
        self.user = os.getenv("DB_USER")
        self.password = os.getenv("DB_PASSWORD")
        self.port = int(os.getenv("DB_PORT") or 3306)

    async def connect(self):
        """Asynchronously establishes a connection pool to the database."""
        try:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                autocommit=True,
                maxsize=10  # Define max connections in the pool
            )
            print("Connected to MySQL (Async)")
            print()
            return self.pool
        except Exception as e:
            print(f"Database connection error: {e}")
            return None

    async def close(self):
        """Closes the connection pool."""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            print("MySQL connection pool closed")

    async def get_connection(self):
        """Get a connection from the pool."""
        if not self.pool:
            print("Database pool is not initialized. Attempting to connect...")
            await self.connect()

        return await self.pool.acquire() if self.pool else None

    async def release_connection(self, connection):
        """Release a connection back to the pool."""
        if self.pool and connection:
            self.pool.release(connection)
