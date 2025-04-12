import sys
from sqlalchemy import text
from database_orm import engine

print(sys.path)


def test_connection():
    try:
        with engine.connect() as connection:
            print("Successfully connected to the database!")

            result = connection.execute(text("SELECT DATABASE();"))
            db_name = result.scalar()

            print(f"Connected to database: {db_name}")
    except Exception as e:
        print(f"Failed to connect to the database: {e}")


if __name__ == "__main__":
    test_connection()

# Testing
# python database_orm_connection_test.py
