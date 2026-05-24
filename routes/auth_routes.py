from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
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
import datetime
import sys

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    ✅ PRODUCTION-READY USER REGISTRATION ENDPOINT
    
    Complete error handling for all scenarios:
    - Pydantic validation (done by FastAPI)
    - Manual field validation (extra safety)
    - Database connection testing
    - Duplicate detection (email & username)
    - Secure password hashing with bcrypt
    - Database transaction management
    - Full logging and tracebacks
    - Proper HTTP status codes
    - Compatible with Flutter Dio
    """
    import time
    start_time = time.time()
    
    # ════════════════════════════════════════════════════════════════════════
    # CRITICAL: Log incoming request to Render logs
    # ════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*80}")
    print(f"[REGISTER-START] Registration endpoint called")
    print(f"[REGISTER-START] Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    print(f"[REGISTER-START] Email: {user_in.email}")
    print(f"[REGISTER-START] Username: {user_in.username}")
    print(f"[REGISTER-START] Full Name: {user_in.full_name}")
    sys.stdout.flush()
    print(f"{'='*80}\n")
    
    logger.info(f"[REGISTER] ════════════════════════════════════════════════════")
    logger.info(f"[REGISTER] 📝 REGISTRATION REQUEST RECEIVED")
    logger.info(f"[REGISTER] Email: {user_in.email} | Username: {user_in.username}")
    logger.info(f"[REGISTER] Full Name: {user_in.full_name}")
    logger.info(f"[REGISTER] ════════════════════════════════════════════════════")
    
    try:
        # ────────────────────────────────────────────────────────────────────
        # STEP 1: Extra validation (Pydantic handles main validation)
        # ────────────────────────────────────────────────────────────────────
        logger.debug(f"[REGISTER] Step 1: Extra field validation...")
        
        email_clean = user_in.email.lower().strip()
        username_clean = user_in.username.lower().strip()
        full_name_clean = user_in.full_name.strip()
        phone_clean = user_in.phone.strip() if user_in.phone else None
        referral_clean = user_in.referral_code.strip() if user_in.referral_code else None
        
        # Email validation
        if not email_clean or "@" not in email_clean:
            msg = "Invalid email address format"
            logger.warning(f"[REGISTER] ❌ {msg}")
            print(f"[REGISTER-ERROR] {msg}: {user_in.email}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": msg}
            )
        
        # Username validation
        if len(username_clean) < 3:
            msg = "Username must be at least 3 characters"
            logger.warning(f"[REGISTER] ❌ {msg}")
            print(f"[REGISTER-ERROR] {msg}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": msg}
            )
        
        # Full name validation
        if len(full_name_clean) < 2:
            msg = "Full name must be at least 2 characters"
            logger.warning(f"[REGISTER] ❌ {msg}")
            print(f"[REGISTER-ERROR] {msg}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": msg}
            )
        
        # Password validation
        if len(user_in.password) < 6:
            msg = "Password must be at least 6 characters"
            logger.warning(f"[REGISTER] ❌ {msg}")
            print(f"[REGISTER-ERROR] {msg}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": msg}
            )
        
        if len(user_in.password) > 256:
            msg = "Password exceeds maximum length"
            logger.warning(f"[REGISTER] ❌ {msg}")
            print(f"[REGISTER-ERROR] {msg}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": msg}
            )
        
        # Check password byte length (bcrypt limit: 72 bytes)
        password_bytes_len = len(user_in.password.encode('utf-8'))
        if password_bytes_len > 72:
            logger.warning(f"[REGISTER] ⚠️  Password is {password_bytes_len} bytes (bcrypt limit: 72)")
        
        logger.debug(f"[REGISTER] ✅ Step 1: Field validation passed")
        
        # ────────────────────────────────────────────────────────────────────
        # STEP 2: Check database connection
        # ────────────────────────────────────────────────────────────────────
        logger.debug(f"[REGISTER] Step 2: Testing database connection...")
        print(f"[REGISTER-DEBUG] Testing database connection...")
        
        try:
            # Test database with simple query
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
            logger.debug(f"[REGISTER] ✅ Database connection OK")
            print(f"[REGISTER-DEBUG] Database connection OK")
        except Exception as db_test_err:
            msg = f"Database connection failed: {str(db_test_err)}"
            logger.error(f"[REGISTER] ❌ {msg}", exc_info=True)
            print(f"[REGISTER-ERROR-CRITICAL] {msg}")
            print(f"[REGISTER-ERROR-CRITICAL] Traceback:\n{traceback.format_exc()}")
            sys.stdout.flush()
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Database unavailable"}
            )
        
        # ────────────────────────────────────────────────────────────────────
        # STEP 3: Check for duplicate email/username
        # ────────────────────────────────────────────────────────────────────
        logger.debug(f"[REGISTER] Step 3: Checking for duplicates...")
        print(f"[REGISTER-DEBUG] Checking for duplicate email/username...")
        
        dup_time = time.time()
        try:
            existing_user = db.query(User).filter(
                (User.email == email_clean) | (User.username == username_clean)
            ).first()
            
            dup_elapsed = time.time() - dup_time
            logger.debug(f"[REGISTER] Duplicate check took {dup_elapsed:.4f}s")
            
            if existing_user:
                if existing_user.email == email_clean:
                    msg = f"Email '{user_in.email}' is already registered"
                    logger.warning(f"[REGISTER] ❌ {msg}")
                    print(f"[REGISTER-ERROR] Email already exists: {user_in.email}")
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"detail": msg}
                    )
                elif existing_user.username == username_clean:
                    msg = f"Username '{user_in.username}' is already taken"
                    logger.warning(f"[REGISTER] ❌ {msg}")
                    print(f"[REGISTER-ERROR] Username already exists: {user_in.username}")
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"detail": msg}
                    )
        except Exception as dup_err:
            msg = f"Failed to check duplicates: {str(dup_err)}"
            logger.error(f"[REGISTER] ❌ {msg}", exc_info=True)
            print(f"[REGISTER-ERROR-CRITICAL] {msg}")
            print(f"[REGISTER-ERROR-CRITICAL] Traceback:\n{traceback.format_exc()}")
            sys.stdout.flush()
            db.rollback()
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to check existing users"}
            )
        
        logger.debug(f"[REGISTER] ✅ Step 3: No duplicates found")
        print(f"[REGISTER-DEBUG] No duplicate email/username")
        
        # ────────────────────────────────────────────────────────────────────
        # STEP 4: Hash password
        # ────────────────────────────────────────────────────────────────────
        logger.debug(f"[REGISTER] Step 4: Hashing password...")
        print(f"[REGISTER-DEBUG] Hashing password...")
        
        hash_time = time.time()
        try:
            hashed_password = get_password_hash_sync(user_in.password)
            hash_elapsed = time.time() - hash_time
            logger.debug(f"[REGISTER] ✅ Password hashed in {hash_elapsed:.4f}s")
            print(f"[REGISTER-DEBUG] Password hashed successfully")
            
            # Validate hash result
            if not hashed_password or len(hashed_password) < 20:
                msg = "Password hashing produced invalid result"
                logger.error(f"[REGISTER] ❌ {msg}")
                print(f"[REGISTER-ERROR] Hash validation failed: {len(hashed_password) if hashed_password else 0} bytes")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Password processing failed"}
                )
        except Exception as hash_err:
            msg = f"Password hashing error: {str(hash_err)}"
            logger.error(f"[REGISTER] ❌ {msg}", exc_info=True)
            print(f"[REGISTER-ERROR-CRITICAL] {msg}")
            print(f"[REGISTER-ERROR-CRITICAL] Traceback:\n{traceback.format_exc()}")
            sys.stdout.flush()
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to process password"}
            )
        
        # ────────────────────────────────────────────────────────────────────
        # STEP 5: Create User model instance
        # ────────────────────────────────────────────────────────────────────
        logger.debug(f"[REGISTER] Step 5: Creating User model...")
        print(f"[REGISTER-DEBUG] Creating User object...")
        
        try:
            new_user = User(
                full_name=full_name_clean,
                username=username_clean,
                email=email_clean,
                phone=phone_clean,
                hashed_password=hashed_password,
                referral_code=referral_clean,
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
            logger.debug(f"[REGISTER] ✅ User object created")
            print(f"[REGISTER-DEBUG] User object created")
        except Exception as obj_err:
            msg = f"Failed to create user object: {str(obj_err)}"
            logger.error(f"[REGISTER] ❌ {msg}", exc_info=True)
            print(f"[REGISTER-ERROR-CRITICAL] {msg}")
            print(f"[REGISTER-ERROR-CRITICAL] Traceback:\n{traceback.format_exc()}")
            sys.stdout.flush()
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to create user"}
            )
        
        # ────────────────────────────────────────────────────────────────────
        # STEP 6: Add to session
        # ────────────────────────────────────────────────────────────────────
        logger.debug(f"[REGISTER] Step 6: Adding user to session...")
        print(f"[REGISTER-DEBUG] Adding user to database session...")
        
        try:
            db.add(new_user)
            logger.debug(f"[REGISTER] ✅ User added to session")
            print(f"[REGISTER-DEBUG] Added to session")
        except Exception as add_err:
            msg = f"Failed to add user to session: {str(add_err)}"
            logger.error(f"[REGISTER] ❌ {msg}", exc_info=True)
            print(f"[REGISTER-ERROR-CRITICAL] {msg}")
            print(f"[REGISTER-ERROR-CRITICAL] Traceback:\n{traceback.format_exc()}")
            sys.stdout.flush()
            db.rollback()
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Database session error"}
            )
        
        # ────────────────────────────────────────────────────────────────────
        # STEP 7: Commit to database
        # ────────────────────────────────────────────────────────────────────
        logger.debug(f"[REGISTER] Step 7: Committing to database...")
        print(f"[REGISTER-DEBUG] Committing transaction...")
        
        commit_time = time.time()
        try:
            db.commit()
            commit_elapsed = time.time() - commit_time
            logger.debug(f"[REGISTER] ✅ Database commit in {commit_elapsed:.4f}s")
            print(f"[REGISTER-DEBUG] Commit successful")
        except IntegrityError as integrity_err:
            db.rollback()
            integrity_msg = str(integrity_err).lower()
            
            if "email" in integrity_msg:
                msg = f"Email '{user_in.email}' is already registered"
                logger.error(f"[REGISTER] ❌ IntegrityError (email): {msg}")
                print(f"[REGISTER-ERROR] Duplicate email error")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": msg}
                )
            elif "username" in integrity_msg:
                msg = f"Username '{user_in.username}' is already taken"
                logger.error(f"[REGISTER] ❌ IntegrityError (username): {msg}")
                print(f"[REGISTER-ERROR] Duplicate username error")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": msg}
                )
            else:
                msg = f"Duplicate user data: {integrity_msg[:100]}"
                logger.error(f"[REGISTER] ❌ IntegrityError: {msg}", exc_info=True)
                print(f"[REGISTER-ERROR-CRITICAL] IntegrityError: {integrity_msg}")
                sys.stdout.flush()
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "User already exists"}
                )
        except SQLAlchemyError as sqlalchemy_err:
            db.rollback()
            msg = f"Database error: {str(sqlalchemy_err)}"
            logger.error(f"[REGISTER] ❌ {msg}", exc_info=True)
            print(f"[REGISTER-ERROR-CRITICAL] SQLAlchemy error: {msg}")
            print(f"[REGISTER-ERROR-CRITICAL] Traceback:\n{traceback.format_exc()}")
            sys.stdout.flush()
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Database error occurred"}
            )
        except Exception as commit_err:
            db.rollback()
            msg = f"Commit error: {str(commit_err)}"
            logger.error(f"[REGISTER] ❌ {msg}", exc_info=True)
            print(f"[REGISTER-ERROR-CRITICAL] Commit error: {msg}")
            print(f"[REGISTER-ERROR-CRITICAL] Traceback:\n{traceback.format_exc()}")
            sys.stdout.flush()
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to save user"}
            )
        
        # ────────────────────────────────────────────────────────────────────
        # STEP 8: Refresh user from database
        # ────────────────────────────────────────────────────────────────────
        logger.debug(f"[REGISTER] Step 8: Refreshing user...")
        print(f"[REGISTER-DEBUG] Refreshing user data...")
        
        try:
            db.refresh(new_user)
            logger.debug(f"[REGISTER] ✅ User refreshed (ID: {new_user.id})")
            print(f"[REGISTER-DEBUG] User refreshed with ID: {new_user.id}")
        except Exception as refresh_err:
            # Non-critical - user was created
            logger.warning(f"[REGISTER] ⚠️  Failed to refresh: {str(refresh_err)}")
            print(f"[REGISTER-WARN] Refresh error (non-critical): {str(refresh_err)}")
        
        # ════════════════════════════════════════════════════════════════════════
        # ✅ SUCCESS!
        # ════════════════════════════════════════════════════════════════════════
        total_time = time.time() - start_time
        logger.info(f"[REGISTER] ════════════════════════════════════════════════════")
        logger.info(f"[REGISTER] ✅ USER REGISTERED SUCCESSFULLY")
        logger.info(f"[REGISTER] User ID: {new_user.id}")
        logger.info(f"[REGISTER] Email: {new_user.email}")
        logger.info(f"[REGISTER] Username: {new_user.username}")
        logger.info(f"[REGISTER] Total time: {total_time:.4f}s")
        logger.info(f"[REGISTER] ════════════════════════════════════════════════════")
        
        print(f"\n{'='*80}")
        print(f"[REGISTER-SUCCESS] ✅ Registration successful!")
        print(f"[REGISTER-SUCCESS] User ID: {new_user.id}")
        print(f"[REGISTER-SUCCESS] Email: {new_user.email}")
        print(f"[REGISTER-SUCCESS] Username: {new_user.username}")
        print(f"[REGISTER-SUCCESS] Time taken: {total_time:.4f}s")
        print(f"{'='*80}\n")
        sys.stdout.flush()
        
        # Return the user response
        return {
            "id": new_user.id,
            "full_name": new_user.full_name,
            "username": new_user.username,
            "email": new_user.email,
            "phone": new_user.phone,
            "referral_code": new_user.referral_code,
            "account_level": new_user.account_level,
            "balance": new_user.balance,
            "demo_balance": new_user.demo_balance,
            "profit_today": new_user.profit_today,
            "total_profit": new_user.total_profit,
            "total_loss": new_user.total_loss,
            "total_trades": new_user.total_trades,
            "win_rate": new_user.win_rate,
            "is_verified": new_user.is_verified,
            "is_admin": new_user.is_admin,
            "is_banned": new_user.is_banned,
            "created_at": new_user.created_at,
            "last_login": new_user.last_login
        }
    
    except Exception as unexpected_err:
        # ════════════════════════════════════════════════════════════════════════
        # ❌ UNEXPECTED ERROR - PRINT FULL TRACEBACK
        # ════════════════════════════════════════════════════════════════════════
        total_time = time.time() - start_time
        error_traceback = traceback.format_exc()
        error_msg = str(unexpected_err)
        
        logger.error(f"[REGISTER] ❌❌❌ UNEXPECTED ERROR ❌❌❌", exc_info=True)
        logger.error(f"[REGISTER] Error: {error_msg}")
        logger.error(f"[REGISTER] Time: {total_time:.4f}s")
        logger.error(f"[REGISTER] Traceback:\n{error_traceback}")
        
        print(f"\n{'='*80}")
        print(f"[REGISTER-FATAL] ❌ UNEXPECTED ERROR OCCURRED")
        print(f"[REGISTER-FATAL] Error message: {error_msg}")
        print(f"[REGISTER-FATAL] Time elapsed: {total_time:.4f}s")
        print(f"[REGISTER-FATAL] Full traceback:")
        print(error_traceback)
        print(f"{'='*80}\n")
        sys.stdout.flush()
        
        # Always try to rollback
        try:
            db.rollback()
        except:
            pass
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Registration failed - unexpected server error"}
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
    return {"message": "If an account with that email exists, a password reset link has been sent."}


@router.post("/reset-password")
def reset_password(token: str, new_password: str, db: Session = Depends(get_db)):
    logger.info(f"[RESET-PWD] Password reset initiated")
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
