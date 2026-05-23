from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database.database import get_db
from models.models import User, Trade, TradeResult
from schemas.schemas import UserResponse, UserUpdate
from auth.auth_bearer import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["user"])

@router.get("/profile", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    logger.info(f"[PROFILE] Fetching profile for user: {current_user.username}")
    logger.debug(f"[PROFILE] User details - ID: {current_user.id}, Email: {current_user.email}")
    logger.info(f"[PROFILE] ✅ Profile fetched successfully")
    return current_user

@router.put("/update-profile", response_model=UserResponse)
def update_profile(
    user_update: UserUpdate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    logger.info(f"[UPDATE-PROFILE] Updating profile for user: {current_user.username}")
    if user_update.full_name:
        current_user.full_name = user_update.full_name
        logger.debug(f"[UPDATE-PROFILE] Updated full_name to: {user_update.full_name}")
    if user_update.phone:
        current_user.phone = user_update.phone
        logger.debug(f"[UPDATE-PROFILE] Updated phone to: {user_update.phone}")
    if user_update.profile_image:
        current_user.profile_image = user_update.profile_image
        logger.debug(f"[UPDATE-PROFILE] Updated profile_image")
    
    db.commit()
    db.refresh(current_user)
    logger.info(f"[UPDATE-PROFILE] ✅ Profile updated successfully")
    return current_user

@router.get("/stats")
def get_user_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info(f"[STATS] Fetching stats for user: {current_user.username}")
    # Recalculate stats on the fly if needed
    win_trades = db.query(Trade).filter(Trade.user_id == current_user.id, Trade.result == TradeResult.WIN).count()
    total_trades = db.query(Trade).filter(Trade.user_id == current_user.id).count()
    
    win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0.0
    
    logger.debug(f"[STATS] Calculated - Win Trades: {win_trades}, Total Trades: {total_trades}, Win Rate: {win_rate}%")
    logger.info(f"[STATS] ✅ Stats fetched successfully")
    
    return {
        "balance": current_user.balance,
        "demo_balance": current_user.demo_balance,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "total_profit": current_user.total_profit,
        "total_loss": current_user.total_loss,
        "profit_today": current_user.profit_today
    }
