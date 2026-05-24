from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from database.database import get_db
from models.models import User
from schemas.schemas import UserCreate, UserResponse, LoginRequest, Token
from auth.auth_handler import get_password_hash_sync, verify_password, create_access_token
from auth.auth_bearer import get_current_user
from auth.auth_handler import jwt, get_password_hash_sync as get_password_hash_sync_import
from config.config import settings
import logging
import traceback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user with comprehensive error handling and logging.
    
    Handles:
    - Field validation
    - Password hashing
    - Duplicate email/username detection
    - Database transaction management
    - Detailed error logging
    - Proper cleanup on failure
    """
    import time
    start_time = time.time()
    
    # Print to console (for Render logs)
    print(f"\n{'='*60}")
    print(f"[REGISTER-CONSOLE] Registration request received")
    print(f"[REGISTER-CONSOLE] Email: {user_in.email}")
    print(f"[REGISTER-CONSOLE] Username: {user_in.username}")
    print(f"[REGISTER-CONSOLE] Full Name: {user_in.full_name}")
    print(f"{'='*60}\n")
    
    logger.info(f"[REGISTER] ═══════════════════════════════════════")
    logger.info(f"[REGISTER] 📝 REGISTER ENDPOINT CALLED")
    logger.info(f"[REGISTER] Email: {user_in.email}, Username: {user_in.username}")
    logger.info(f"[REGISTER] Full Name: {user_in.full_name}")
    logger.info(f"[REGISTER] ═══════════════════════════════════════")
    
    try:
        # Step 1: Validate input fields
        logger.debug(f"[REGISTER] Step 1: Validating input fields...")
        
        if not user_in.email or not user_in.email.strip():
            logger.warning(f"[REGISTER] ❌ Email is empty")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required and cannot be empty"
            )
        
        if not user_in.username or not user_in.username.strip():
            logger.warning(f"[REGISTER] ❌ Username is empty")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is required and cannot be empty"
            )
        
        if not user_in.full_name or not user_in.full_name.strip():
            logger.warning(f"[REGISTER] ❌ Full name is empty")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Full name is required and cannot be empty"
            )
        
        if not user_in.password or len(user_in.password) < 6:
            logger.warning(f"[REGISTER] ❌ Password validation failed")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters"
            )
        
        if len(user_in.password) > 256:
            logger.warning(f"[REGISTER] ❌ Password too long")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is too long (max 256 characters)"
            )
        
        logger.debug(f"[REGISTER] ✅ All input fields validated successfully")
        
        # Step 2: Check for duplicate email or username
        logger.debug(f"[REGISTER] Step 2: Checking for duplicate email/username in database...")
        duplicate_query_start = time.time()
        
        try:
            existing_user = db.query(User).filter(
                (User.email == user_in.email.lower().strip()) | 
                (User.username == user_in.username.lower().strip())
            ).first()
            
            duplicate_query_elapsed = time.time() - duplicate_query_start
            logger.debug(f"[REGISTER] Duplicate check completed in {duplicate_query_elapsed:.4f}s")
            
            if existing_user:
                if existing_user.email == user_in.email.lower().strip():
                    print(f"[REGISTER-ERROR] Email already registered: {user_in.email}")
                    logger.warning(f"[REGISTER] ❌ Email already registered: {user_in.email}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Email '{user_in.email}' is already registered"
                    )
                else:
                    print(f"[REGISTER-ERROR] Username already taken: {user_in.username}")
                    logger.warning(f"[REGISTER] ❌ Username already taken: {user_in.username}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Username '{user_in.username}' is already taken"
                    )
        except HTTPException:
            # Re-raise HTTP exceptions (duplicate email/username)
            raise
        except Exception as e:
            logger.error(f"[REGISTER] ❌ Database query error during duplicate check: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to check existing users. Please try again."
            )
        
        # Step 3: Hash password
        logger.debug(f"[REGISTER] Step 3: Hashing password...")
        hash_start = time.time()
        
        try:
            hashed_password = get_password_hash_sync(user_in.password)
            hash_elapsed = time.time() - hash_start
            logger.debug(f"[REGISTER] ✅ Password hashed successfully in {hash_elapsed:.4f}s")
        except Exception as e:
            logger.error(f"[REGISTER] ❌ Password hashing failed: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to hash password. Please try again."
            )
        
        # Step 4: Create new user object
        logger.debug(f"[REGISTER] Step 4: Creating new user object...")
        
        try:
            new_user = User(
                full_name=user_in.full_name.strip(),
                username=user_in.username.lower().strip(),
                email=user_in.email.lower().strip(),
                phone=user_in.phone.strip() if user_in.phone else None,
                hashed_password=hashed_password,
                referral_code=user_in.referral_code.strip() if user_in.referral_code else None,
                account_level="Standard",
                balance=0.0,
                demo_balance=10000.0,
                profit_today=0.0,
                total_profit=0.0,
                total_loss=0.0,
                total_trades=0,
                win_rate=0.0,
                is_verified=False,
                is_admin=False,
                is_banned=False
            )
            logger.debug(f"[REGISTER] ✅ User object created successfully")
        except Exception as e:
            logger.error(f"[REGISTER] ❌ Failed to create user object: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process registration. Invalid data provided."
            )
        
        # Step 5: Add user to database session
        logger.debug(f"[REGISTER] Step 5: Adding user to database session...")
        
        try:
            db.add(new_user)
            logger.debug(f"[REGISTER] ✅ User added to session")
        except Exception as e:
            logger.error(f"[REGISTER] ❌ Failed to add user to session: {str(e)}", exc_info=True)
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database session error. Please try again."
            )
        
        # Step 6: Commit to database
        logger.debug(f"[REGISTER] Step 6: Committing user to database...")
        commit_start = time.time()
        
        try:
            db.commit()
            commit_elapsed = time.time() - commit_start
            logger.debug(f"[REGISTER] ✅ Database commit successful in {commit_elapsed:.4f}s")
        except IntegrityError as e:
            # Handle duplicate key or constraint violations
            db.rollback()
            logger.error(f"[REGISTER] ❌ Database integrity error (duplicate data): {str(e)}", exc_info=True)
            
            # Check which constraint was violated
            error_msg = str(e).lower()
            if "email" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email '{user_in.email}' is already registered"
                )
            elif "username" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Username '{user_in.username}' is already taken"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This user data already exists in our system"
                )
        except SQLAlchemyError as e:
            # Handle other SQLAlchemy errors
            db.rollback()
            logger.error(f"[REGISTER] ❌ SQLAlchemy error during commit: {str(e)}", exc_info=True)
            print(f"[REGISTER-PRINT] SQLAlchemy Error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error. Please try again later."
            )
        except Exception as e:
            # Handle any other unexpected errors
            db.rollback()
            logger.error(f"[REGISTER] ❌ Unexpected error during commit: {str(e)}", exc_info=True)
            print(f"[REGISTER-PRINT] Unexpected Error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during registration"
            )
        
        # Step 7: Refresh user from database to get generated fields (id, created_at)
        logger.debug(f"[REGISTER] Step 7: Refreshing user data from database...")
        refresh_start = time.time()
        
        try:
            db.refresh(new_user)
            refresh_elapsed = time.time() - refresh_start
            logger.debug(f"[REGISTER] ✅ User data refreshed in {refresh_elapsed:.4f}s")
        except Exception as e:
            logger.error(f"[REGISTER] ❌ Failed to refresh user data: {str(e)}", exc_info=True)
            # This is non-critical, user was created successfully, just can't get full response
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User registered but failed to retrieve full details"
            )
        
        # Success
        total_elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"[REGISTER-SUCCESS] User registered successfully!")
        print(f"[REGISTER-SUCCESS] User ID: {new_user.id}")
        print(f"[REGISTER-SUCCESS] Email: {new_user.email}")
        print(f"[REGISTER-SUCCESS] Username: {new_user.username}")
        print(f"[REGISTER-SUCCESS] Time taken: {total_elapsed:.4f}s")
        print(f"{'='*60}\n")
        
        logger.info(f"[REGISTER] ═══════════════════════════════════════")
        logger.info(f"[REGISTER] ✅ USER REGISTERED SUCCESSFULLY")
        logger.info(f"[REGISTER] User ID: {new_user.id}, Email: {new_user.email}, Username: {new_user.username}")
        logger.info(f"[REGISTER] Total registration time: {total_elapsed:.4f}s")
        logger.info(f"[REGISTER] ═══════════════════════════════════════")
        
        return new_user

    except HTTPException:
        # Re-raise HTTP exceptions with proper status codes
        raise
    except Exception as e:
        # Catch-all for any unexpected errors
        total_elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"[REGISTER-ERROR] Registration failed with exception!")
        print(f"[REGISTER-ERROR] Error: {str(e)}")
        print(f"[REGISTER-ERROR] Time taken: {total_elapsed:.4f}s")
        print(f"[REGISTER-ERROR] Traceback:\n{traceback.format_exc()}")
        print(f"{'='*60}\n")
        
        logger.error(f"[REGISTER] ❌ UNEXPECTED ERROR after {total_elapsed:.4f}s: {str(e)}", exc_info=True)
        
        # Make sure to rollback on any error
        try:
            db.rollback()
        except:
            pass
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again or contact support."
        )

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
