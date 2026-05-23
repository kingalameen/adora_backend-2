import os
import secrets
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "adora backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    CORS_ORIGINS: list = ["*"] # Change to specific domains in production

    # Database Settings
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATABASE_URL: str = ""

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))

    # Default Admin
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "kingalameen@admin.com")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "kingalameenadmin")

    # Market Settings
    MARKET_UPDATE_INTERVAL: int = 1  # seconds
    # Mapping: our display names → asset symbol names
    ASSETS: list = ["BTC/USD", "ETH/USD", "EUR/USD", "GOLD"]

    # Trading logic
    PAYOUT_PERCENTAGE: float = 0.8  # 80%

    # ── CoinGecko ───────────────────────────────────────────────────────────
    COINGECKO_API_KEY: str = ""

    # ── Paystack ────────────────────────────────────────────────────────────
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        # Initialize DATABASE_URL if not set
        if not self.DATABASE_URL:
            self.DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(self.BASE_DIR, 'adora.db')}")
        
        # SQLAlchemy 1.4+ and 2.0 require 'postgresql://' instead of 'postgres://'
        if self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
        # Handle relative sqlite paths
        if self.DATABASE_URL.startswith("sqlite:///") and not self.DATABASE_URL.startswith("sqlite:////"):
            relative_path = self.DATABASE_URL.replace("sqlite:///", "")
            if not os.path.isabs(relative_path):
                self.DATABASE_URL = f"sqlite:///{os.path.join(self.BASE_DIR, relative_path)}"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"

settings = Settings()
