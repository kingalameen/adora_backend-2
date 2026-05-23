from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from database.database import get_db
from config.config import settings
from models.models import User
from auth.auth_handler import TokenData
import logging

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    """Extract and validate JWT token, return current user."""
    logger.debug(f"[AUTH-BEARER] Validating token...")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        logger.debug(f"[AUTH-BEARER] Decoding JWT token...")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            logger.warning(f"[AUTH-BEARER] No 'sub' in token payload")
            raise credentials_exception
        token_data = TokenData(username=username)
        logger.debug(f"[AUTH-BEARER] Token decoded successfully for user: {username}")
    except JWTError as e:
        logger.warning(f"[AUTH-BEARER] JWT decode error: {e}")
        raise credentials_exception
    
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        logger.warning(f"[AUTH-BEARER] User not found: {token_data.username}")
        raise credentials_exception
    if user.is_banned:
        logger.warning(f"[AUTH-BEARER] User is banned: {user.username}")
        raise HTTPException(status_code=403, detail="User is banned")
    
    logger.debug(f"[AUTH-BEARER] ✅ User authenticated: {user.username}")
    return user

def get_current_admin(current_user: User = Depends(get_current_user)):
    """Verify current user is an admin."""
    logger.debug(f"[AUTH-BEARER] Checking admin privileges for: {current_user.username}")
    if not current_user.is_admin:
        logger.warning(f"[AUTH-BEARER] ❌ User is not admin: {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    logger.debug(f"[AUTH-BEARER] ✅ Admin privileges confirmed for: {current_user.username}")
    return current_user
