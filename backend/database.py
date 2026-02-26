import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv() # Load variables from .env

# Use the Supabase / PostgreSQL URL if provided in environment variables.
# Fallback to local SQLite for local testing if no env variable is found.
db_url = os.getenv(
    "DATABASE_URL", 
    "sqlite:///./afl_betting.db"
)

# Render and Supabase often have IPv6 connection issues on port 5432.
# We force the connection string to use the transaction pooler port 6543
# which guarantees an IPv4 proxy connection if using Supabase.
if "supabase.co:5432" in db_url:
    db_url = db_url.replace(":5432", ":6543")

SQLALCHEMY_DATABASE_URL = db_url

# Connect args needed for SQLite, but shouldn't be used for Postgres
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # Supabase / PostgreSQL connection
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
