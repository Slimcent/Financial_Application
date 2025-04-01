from database_orm import Base, engine
import models.user

print(Base.metadata.tables.keys())

print("Tables found:", Base.metadata.tables.keys())

# Base.metadata.create_all(engine)

# to test in terminal
# python test_db.py
