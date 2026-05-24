import asyncio
import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler
from config.config import settings
from database.database import engine, Base, SessionLocal
from models import models
from routes import auth_routes, user_routes, wallet_routes, trade_routes, ws_routes, notification_routes, admin_routes, market_routes
from services.market_simulator import market_simulator
from services.trade_engine import trade_engine
from services.dexscreener_client import dexscreener_client
from auth.auth_handler import get_password_hash_sync
from websocket.manager import manager
from schemas.schemas import MarketPriceResponse
import logging
import time

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create database tables with error handling
logger.info(f"[STARTUP] Creating database tables...")
try:
    Base.metadata.create_all(bind=engine)
    logger.info(f"[STARTUP] ✅ Database tables created successfully")
except Exception as e:
    logger.error(f"[STARTUP] ❌ Failed to create database tables: {str(e)}", exc_info=True)
    print(f"[STARTUP-PRINT] ERROR creating tables: {str(e)}")
    raise

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response timeout middleware to ensure endpoints respond quickly
@app.middleware("http")
async def enforce_response_timeout(request: Request, call_next):
    """Ensure all endpoints respond within reasonable time."""
    start_time = time.time()
    path = request.url.path
    method = request.method
    
    try:
        # Set a per-request timeout of 30 seconds
        response = await asyncio.wait_for(call_next(request), timeout=30.0)
        elapsed = time.time() - start_time
        logger.debug(f"[RESPONSE] {method} {path} completed in {elapsed:.2f}s")
        return response
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        logger.error(f"[RESPONSE] ❌ {method} {path} TIMEOUT after {elapsed:.2f}s (>30s)")
        return JSONResponse(
            status_code=504,
            content={"detail": "Request timeout - server took too long to respond"}
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[RESPONSE] ❌ {method} {path} ERROR after {elapsed:.2f}s: {e}")
        raise

# Include Routers
app.include_router(auth_routes.router, prefix=settings.API_V1_STR)
app.include_router(user_routes.router, prefix=settings.API_V1_STR)
app.include_router(wallet_routes.router, prefix=settings.API_V1_STR)
app.include_router(trade_routes.router, prefix=settings.API_V1_STR)
app.include_router(market_routes.router, prefix=settings.API_V1_STR)
app.include_router(notification_routes.router, prefix=settings.API_V1_STR)
app.include_router(admin_routes.router, prefix=settings.API_V1_STR)
app.include_router(ws_routes.router)

# Health check endpoint for Render
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "adora-backend"}

# Diagnostic endpoint for debugging registration issues
@app.get("/api/debug/registration")
async def debug_registration():
    """
    Diagnostic endpoint to verify registration system is working.
    Returns database status, user count, and column information.
    """
    try:
        logger.info(f"[DEBUG] Registration diagnostic check requested")
        
        db = SessionLocal()
        try:
            # Test database connection
            user_count = db.query(models.User).count()
            logger.info(f"[DEBUG] User count: {user_count}")
            
            # Get table columns
            user_table_columns = [col.name for col in models.User.__table__.columns]
            logger.info(f"[DEBUG] User table columns: {user_table_columns}")
            
            # Check if admin exists
            admin = db.query(models.User).filter(models.User.email == settings.ADMIN_EMAIL).first()
            admin_exists = admin is not None
            
            return {
                "status": "ok",
                "database": "connected",
                "user_count": user_count,
                "user_table_columns": user_table_columns,
                "admin_exists": admin_exists,
                "admin_email": settings.ADMIN_EMAIL if admin_exists else None,
                "database_url": "sqlite" if "sqlite" in settings.DATABASE_URL else "postgresql"
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[DEBUG] Diagnostic check failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to run diagnostic checks"
        }

def setup_default_admin():
    """Create default admin user if not exists."""
    db = SessionLocal()
    try:
        logger.info(f"[ADMIN-SETUP] Starting default admin setup...")
        # Check for the NEW admin email specifically
        admin = db.query(models.User).filter(models.User.email == settings.ADMIN_EMAIL).first()
        if not admin:
            logger.info(f"[ADMIN-SETUP] Creating new default admin user: {settings.ADMIN_EMAIL}")
            logger.debug(f"[ADMIN-SETUP] Hashing admin password...")
            # Ensure password is safe
            admin_pass = settings.ADMIN_PASSWORD[:72] if settings.ADMIN_PASSWORD else "admin123"
            hashed_password = get_password_hash_sync(admin_pass)
            logger.debug(f"[ADMIN-SETUP] Admin password hashed, creating user record...")
            new_admin = models.User(
                full_name="ABBANDAYA Admin",
                username="admin",
                email=settings.ADMIN_EMAIL,
                hashed_password=hashed_password,
                is_admin=True,
                is_verified=True,
                balance=0.0,
                demo_balance=10000.0
            )
            db.add(new_admin)
            db.commit()
            logger.info(f"[ADMIN-SETUP] ✅ New admin created successfully: {settings.ADMIN_EMAIL}")
        else:
            # Ensure they are actually an admin and have the correct password
            if not admin.is_admin:
                admin.is_admin = True
                db.commit()
                logger.info(f"[ADMIN-SETUP] Promoted {settings.ADMIN_EMAIL} to admin.")
            else:
                logger.debug(f"[ADMIN-SETUP] Admin user already exists and is properly configured")
    except Exception as e:
        logger.error(f"[ADMIN-SETUP] ❌ Error setting up default admin: {e}", exc_info=True)
    finally:
        db.close()

# Background Tasks
def market_update_task():
    # market_simulator.update_prices() # No longer needed, Deriv handles updates
    trade_engine.process_expired_trades()

async def broadcast_market_prices():
    logger.info("Market broadcasting task started")
    while True:
        try:
            # We broadcast the latest prices from the database/cache for speed
            db = SessionLocal()
            try:
                markets = db.query(models.MarketPrice).all()
                candle_state = dexscreener_client.get_candle_state()
                data = {
                    m.symbol: {
                        "price": m.current_price,
                        "change": m.percentage_change,
                        "candle": candle_state.get(m.symbol)
                    } for m in markets
                }
                if data:
                    logger.info(f"Broadcasting market update to {len(manager.active_connections.get('market', []))} clients")
                    await manager.broadcast({
                        "type": "market_update", 
                        "data": data,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }, "market")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error in broadcast_market_prices: {e}")
            await asyncio.sleep(2) # Wait a bit on error
        await asyncio.sleep(settings.MARKET_UPDATE_INTERVAL)

@app.on_event("startup")
async def startup_event():
    # Ensure metadata column exists in transactions table
    try:
        with engine.begin() as conn:
            from sqlalchemy import text
            try:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN tx_metadata VARCHAR;"))
                logger.info("✅ Added tx_metadata column to transactions table.")
            except Exception as e:
                logger.debug(f"tx_metadata column might already exist: {e}")
    except Exception as e:
        logger.error(f"❌ Database startup error: {e}", exc_info=True)

    setup_default_admin()
    market_simulator.initialize_market()
    
    # Seed candles in background (non-blocking)
    asyncio.create_task(_seed_candles_background())
    asyncio.create_task(dexscreener_client.run())
    
    # Start the scheduler for trade processing
    scheduler = BackgroundScheduler()
    scheduler.add_job(market_update_task, 'interval', seconds=settings.MARKET_UPDATE_INTERVAL * 5)
    scheduler.start()
    
    # Start the async broadcasting task
    asyncio.create_task(broadcast_market_prices())
    
    logger.info("ABBANDAYA Backend Started Successfully")

async def _seed_candles_background():
    """Run seed_missing_candles in background without blocking startup."""
    await asyncio.sleep(0.1)  # Yield to let server fully start
    try:
        logger.info("[STARTUP] Running candle seed in background...")
        # Run in thread pool to not block event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, dexscreener_client.seed_missing_candles)
        logger.info("[STARTUP] ✅ Candle seed completed")
    except Exception as e:
        logger.error(f"[STARTUP] Error seeding candles: {e}", exc_info=True)

@app.get("/")
async def root():
    return {"message": "Welcome to ABBANDAYA Backend API", "version": settings.VERSION}

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
