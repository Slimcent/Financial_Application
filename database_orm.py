import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load environment variables
load_dotenv()

print(".env loaded")

# Database connection URL
DATABASE_URL = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}" \
               f":{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=True)

# Base class for models
Base = declarative_base()

# Session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

