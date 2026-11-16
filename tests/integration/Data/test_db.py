from Data.database_orm import Base, engine
import Models.Entities.user

print(Base.metadata.tables.keys())

print("Tables found:", Base.metadata.tables.keys())

# Base.metadata.create_all(engine)

# to test in terminal
# python -m tests.integration.Data.test_db   (run from the project root)
