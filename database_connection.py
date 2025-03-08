import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Check if DB_PORT is retrieved
port = os.getenv("DB_PORT")

if port is None:
    raise ValueError("Error: DB_PORT is missing or not loaded from the .env file")

# Convert DB_PORT to integer
port = int(port)


def create_connection():
    try:
        # Get database credentials
        hostname = os.getenv("DB_HOST")
        database = os.getenv("DB_NAME")
        username = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")

        if not all([hostname, database, username, password]):
            raise ValueError(" Missing required database credentials in .env file")

        # Establish connection
        connection = mysql.connector.connect(
            host=hostname,
            database=database,
            user=username,
            password=password,
            port=port
        )

        if connection.is_connected():
            print("Connected to MySQL Server")
            return connection

    except Error as e:
        print("Error while connecting to MySQL:", e)
        return None

    except ValueError as ve:
        print(ve)
        return None


def check_database():
    # check database connection
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT DATABASE();")
            record = cursor.fetchone()
            print("Connected to database:", record)
        except Exception as e:
            print("Error executing query:", e)
        finally:
            cursor.close()
            connection.close()
            print("MySQL connection is closed")
