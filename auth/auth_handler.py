from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from config.config import settings
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Thread pool for CPU-intensive bcrypt operations
_executor = ThreadPoolExecutor(max_workers=4)

class TokenData(BaseModel):
    username: Optional[str] = None

pwd_context = CryptContext(
    schemes=["bcrypt"], 
    deprecated="auto",
    bcrypt__rounds=12  # Explicit rounds to control speed
)

def verify_password_sync(plain_password, hashed_password):
    """Synchronous password verification (for non-async contexts)."""
    try:
        logger.debug(f"[VERIFY] Starting bcrypt verify_password_sync")
        result = pwd_context.verify(plain_password, hashed_password)
        logger.debug(f"[VERIFY] Password verification result: {result}")
        return result
    except Exception as e:
        logger.error(f"[VERIFY] Password verification error: {e}")
        return False

async def verify_password(plain_password, hashed_password):
    """Async password verification using thread pool to prevent blocking."""
    try:
        logger.debug(f"[VERIFY-ASYNC] Starting async password verification")
        # Run blocking bcrypt in thread pool with timeout
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(_executor, pwd_context.verify, plain_password, hashed_password),
            timeout=5.0  # 5 second timeout on bcrypt
        )
        logger.debug(f"[VERIFY-ASYNC] Password verification completed: {result}")
        return result
    except asyncio.TimeoutError:
        logger.error(f"[VERIFY-ASYNC] ❌ Password verification TIMEOUT after 5 seconds!")
        return False
    except Exception as e:
        logger.error(f"[VERIFY-ASYNC] Password verification error: {e}")
        return False

def get_password_hash_sync(password):
    """Synchronous password hashing."""
    try:
        logger.debug(f"[HASH] Starting password hash")
        hashed = pwd_context.hash(password)
        logger.debug(f"[HASH] Password hash completed successfully")
        return hashed
    except Exception as e:
        logger.error(f"[HASH] Password hashing error: {e}")
        raise

async def get_password_hash(password):
    """Async password hashing using thread pool."""
    try:
        logger.debug(f"[HASH-ASYNC] Starting async password hash")
        loop = asyncio.get_event_loop()
        hashed = await asyncio.wait_for(
            loop.run_in_executor(_executor, pwd_context.hash, password),
            timeout=10.0  # 10 second timeout on hash
        )
        logger.debug(f"[HASH-ASYNC] Password hash completed successfully")
        return hashed
    except asyncio.TimeoutError:
        logger.error(f"[HASH-ASYNC] ❌ Password hashing TIMEOUT after 10 seconds!")
        raise Exception("Password hashing timeout")
    except Exception as e:
        logger.error(f"[HASH-ASYNC] Password hashing error: {e}")
        raise

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    try:
        logger.debug(f"[JWT] Creating access token for user: {data.get('sub')}")
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(datetime.timezone.utc) + expires_delta
        else:
            expire = datetime.now(datetime.timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        logger.debug(f"[JWT] ✅ Access token created successfully")
        return encoded_jwt
    except Exception as e:
        logger.error(f"[JWT] Token creation error: {e}")
        raise
