from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from config.config import settings
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# BCRYPT PASSWORD LIMIT: 72 bytes (bcrypt truncates silently if longer)
BCRYPT_MAX_BYTES = 72

# Thread pool for CPU-intensive bcrypt operations
_executor = ThreadPoolExecutor(max_workers=4)

def _truncate_password(password: str) -> str:
    """
    Truncate password to 72 bytes max (bcrypt limit) safely.
    
    IMPORTANT: Properly handles UTF-8 by truncating at character boundaries,
    not at arbitrary byte positions to prevent corruption.
    """
    try:
        encoded = password.encode('utf-8')
        
        if len(encoded) <= BCRYPT_MAX_BYTES:
            return password
        
        # Truncate byte string and safely decode, handling incomplete characters
        truncated_bytes = encoded[:BCRYPT_MAX_BYTES]
        
        # Try to decode, removing incomplete UTF-8 sequences from the end
        for i in range(len(truncated_bytes), 0, -1):
            try:
                decoded = truncated_bytes[:i].decode('utf-8')
                logger.debug(f"[PASSWORD] Password truncated from {len(encoded)} to {i} bytes (safe UTF-8 boundary)")
                return decoded
            except UnicodeDecodeError:
                # Byte at position i breaks UTF-8, try smaller
                continue
        
        # Fallback: should never reach here if password had at least 1 byte
        logger.warning("[PASSWORD] Failed to safely truncate password, using original")
        return password
    except Exception as e:
        logger.error(f"[PASSWORD] Error truncating password: {e}")
        return password

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
        # Truncate password to 72 bytes (bcrypt limit)
        truncated = _truncate_password(plain_password)
        result = pwd_context.verify(truncated, hashed_password)
        logger.debug(f"[VERIFY] Password verification result: {result}")
        return result
    except Exception as e:
        logger.error(f"[VERIFY] Password verification error: {e}")
        return False

async def verify_password(plain_password, hashed_password):
    """Async password verification using thread pool to prevent blocking."""
    try:
        logger.debug(f"[VERIFY-ASYNC] Starting async password verification")
        # Truncate password to 72 bytes (bcrypt limit)
        truncated = _truncate_password(plain_password)
        logger.debug(f"[VERIFY-ASYNC] Password truncated to {len(truncated.encode('utf-8'))} bytes")
        # Run blocking bcrypt in thread pool with timeout
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(_executor, pwd_context.verify, truncated, hashed_password),
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
        # Truncate password to 72 bytes (bcrypt limit)
        truncated = _truncate_password(password)
        hashed = pwd_context.hash(truncated)
        logger.debug(f"[HASH] Password hash completed successfully")
        return hashed
    except Exception as e:
        logger.error(f"[HASH] Password hashing error: {e}")
        raise

async def get_password_hash(password):
    """Async password hashing using thread pool."""
    try:
        logger.debug(f"[HASH-ASYNC] Starting async password hash")
        # Truncate password to 72 bytes (bcrypt limit)
        truncated = _truncate_password(password)
        loop = asyncio.get_event_loop()
        hashed = await asyncio.wait_for(
            loop.run_in_executor(_executor, pwd_context.hash, truncated),
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
    """Create JWT access token with proper UTC timezone handling."""
    try:
        logger.debug(f"[JWT] Creating access token for user: {data.get('sub')}")
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        logger.debug(f"[JWT] ✅ Access token created successfully")
        return encoded_jwt
    except Exception as e:
        logger.error(f"[JWT] Token creation error: {e}", exc_info=True)
        raise
