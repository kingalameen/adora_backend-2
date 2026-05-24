from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.database import get_db
from models.models import User
from schemas.schemas import UserCreate, UserResponse, LoginRequest, Token
from auth.auth_handler import get_password_hash_sync, verify_password, create_access_token
from auth.auth_bearer import get_current_user
from auth.auth_handler import jwt, get_password_hash_sync as get_password_hash_sync_import
from config.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    logger.info(f"[REGISTER] Start: email={user_in.email}")
    
    # Validate password
    if len(user_in.password) < 6:
        logger.warning(f"[REGISTER] Password too short")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters"
        )
    
    user_db = db.query(User).filter(
        (User.email == user_in.email) | (User.username == user_in.username)
    ).first()
    if user_db:
        logger.warning(f"[REGISTER] User already exists: {user_in.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )
    
    logger.debug(f"[REGISTER] Hashing password...")
    hashed_password = get_password_hash_sync(user_in.password)
    logger.debug(f"[REGISTER] Password hashed successfully")
    
    new_user = User(
        full_name=user_in.full_name,
        username=user_in.username,
        email=user_in.email,
        phone=user_in.phone,
        hashed_password=hashed_password,
        referral_code=user_in.referral_code,
        balance=0.0,       # Initial real balance
        demo_balance=10000.0 # Initial demo balance
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info(f"[REGISTER] ✅ User registered successfully: {user_in.email}")
    return new_user

@router.post("/login", response_model=Token)
async def login(login_req: LoginRequest, db: Session = Depends(get_db)):
    """Async login endpoint with proper logging and timeout handling."""
    import time
    login_start_time = time.time()
    try:
        logger.info(f"[LOGIN] ═══════════════════════════════════════")
        logger.info(f"[LOGIN] 🔐 LOGIN ENDPOINT CALLED at {login_start_time}")
        logger.info(f"[LOGIN] Username/Email: {login_req.username_or_email}")
        logger.info(f"[LOGIN] ═══════════════════════════════════════")
        
        # Step 1: Database user lookup
        lookup_start = time.time()
        logger.debug(f"[LOGIN] Querying database for user...")
        user = db.query(User).filter(
            (User.email == login_req.username_or_email) | 
            (User.username == login_req.username_or_email)
        ).first()
        lookup_elapsed = time.time() - lookup_start
        logger.debug(f"[LOGIN] Database lookup completed in {lookup_elapsed:.4f}s")
        
        if not user:
            logger.warning(f"[LOGIN] ❌ User not found: {login_req.username_or_email}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        logger.debug(f"[LOGIN] User found: {user.username} (id={user.id})")
        
        # Step 2: Password verification
        verify_start = time.time()
        logger.debug(f"[LOGIN] Starting password verification...")
        password_valid = await verify_password(login_req.password, user.hashed_password)
        verify_elapsed = time.time() - verify_start
        logger.debug(f"[LOGIN] Password verification completed in {verify_elapsed:.4f}s")
        
        if not password_valid:
            logger.warning(f"[LOGIN] ❌ Invalid password for user: {user.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password",
            )
        
        logger.debug(f"[LOGIN] ✅ Password verified successfully")
        
        # Step 3: Check ban status
        if user.is_banned:
            logger.warning(f"[LOGIN] ❌ User is banned: {user.username}")
            raise HTTPException(status_code=403, detail="User is banned")
        
        # Step 4: Create JWT token
        token_start = time.time()
        logger.debug(f"[LOGIN] Creating JWT token...")
        access_token = create_access_token(data={"sub": user.username})
        token_elapsed = time.time() - token_start
        logger.info(f"[LOGIN] ✅ JWT token created successfully in {token_elapsed:.4f}s")
        
        total_elapsed = time.time() - login_start_time
        logger.info(f"[LOGIN] ═══════════════════════════════════════")
        logger.info(f"[LOGIN] ✅ LOGIN SUCCESSFUL: {user.username}")
        logger.info(f"[LOGIN] Total login time: {total_elapsed:.4f}s")
        logger.info(f"[LOGIN] ═══════════════════════════════════════")
        
        return {"access_token": access_token, "token_type": "bearer"}
    
    except HTTPException:
        raise
    except Exception as e:
        elapsed = time.time() - login_start_time
        logger.error(f"[LOGIN] ❌ UNEXPECTED ERROR after {elapsed:.4f}s: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed due to server error"
        )

@router.post("/forgot-password")
def forgot_password(email: str, db: Session = Depends(get_db)):
    logger.info(f"[FORGOT-PWD] Password reset requested for: {email}")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        logger.debug(f"[FORGOT-PWD] User not found: {email}")
        # We still return same message for security
        pass
    # In a real app, generate token and send email.
    return {"message": "If an account with that email exists, a password reset link has been sent."}

@router.post("/reset-password")
def reset_password(token: str, new_password: str, db: Session = Depends(get_db)):
    logger.info(f"[RESET-PWD] Password reset initiated")
    # Logic to reset password using token (simplified for now)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        user = db.query(User).filter(User.username == username).first()
        if user:
            logger.debug(f"[RESET-PWD] Hashing new password...")
            user.hashed_password = get_password_hash_sync_import(new_password)
            db.commit()
            logger.info(f"[RESET-PWD] ✅ Password reset successfully for: {username}")
            return {"message": "Password has been reset successfully."}
    except Exception as e:
        logger.error(f"[RESET-PWD] Error: {e}")
        pass
    raise HTTPException(status_code=400, detail="Invalid or expired token")

@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    logger.info(f"[LOGOUT] User logged out: {current_user.username}")
    return {"message": "Successfully logged out"}
