import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()


class DatabaseConnection:
    def __init__(self):
        self.connection = None
        self.port = int(os.getenv("DB_PORT") or 3306)

    def connect(self):
        """Establishes a database connection."""
        try:
            self.connection = mysql.connector.connect(
                host=os.getenv("DB_HOST"),
                database=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                port=self.port
            )
            print("Connected to MySQL")
            return self.connection
        except Error as e:
            print("Database connection error:", e)
            return None

    def close(self):
        """Closes the connection."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("MySQL connection closed")
