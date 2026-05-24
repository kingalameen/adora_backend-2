from sqlalchemy import create_engine, event, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config.config import settings
import logging

logger = logging.getLogger(__name__)

# Optimize engine for SQLite (or PostgreSQL if configured)
engine_kwargs = {
    "connect_args": {"check_same_thread": False},
    "echo": False  # Set to True for SQL debugging
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
    engine_kwargs["pool_pre_ping"] = True  # Verify connections before use

logger.debug(f"[DATABASE] Creating engine with URL: {settings.DATABASE_URL}")
logger.debug(f"[DATABASE] Engine kwargs: {engine_kwargs}")

try:
    engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
    logger.info("[DATABASE] ✓ Engine created successfully")
except Exception as e:
    logger.error(f"[DATABASE] ✗ Failed to create engine: {e}", exc_info=True)
    raise

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Optimize SQLite for better concurrency and performance."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=10000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()
        logger.debug("[DATABASE] SQLite PRAGMAs configured")
    except Exception as e:
        logger.debug(f"[DATABASE] Could not set PRAGMAs (might be PostgreSQL): {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    Get database session with proper cleanup.
    
    CRITICAL: This dependency ensures:
    - Each request gets its own session
    - Sessions are ALWAYS closed, even on error
    - No connection leaks
    """
    db = SessionLocal()
    try:
        logger.debug("[DATABASE] Session created for request")
        yield db
    except Exception as e:
        logger.error(f"[DATABASE] Error in session, rolling back: {e}")
        try:
            db.rollback()
        except:
            pass
        raise
    finally:
        try:
            db.close()
            logger.debug("[DATABASE] Session closed for request")
        except Exception as e:
            logger.warning(f"[DATABASE] Error closing session: {e}")
