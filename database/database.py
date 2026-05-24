from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.config import settings
import logging

logger = logging.getLogger(__name__)

# Optimize engine for SQLite (or PostgreSQL if configured)
engine_kwargs = {
    "connect_args": {"check_same_thread": False},
}

# Add connection pooling for better concurrency
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite doesn't benefit from large pools, use small pool
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10
else:
    # PostgreSQL - use larger pool for production
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 40

logger.debug(f"[DATABASE] Creating engine with kwargs: {engine_kwargs}")
engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Optimize SQLite for better concurrency and performance."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=10000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Get database session with proper cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
