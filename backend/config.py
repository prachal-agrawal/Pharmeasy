from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application-wide settings loaded from environment / .env file.

    All fields can be overridden via environment variables or a ``.env`` file
    placed in the backend directory.

    Attributes:
        PORT: Uvicorn listen port.
        DEBUG: Enable debug mode.
        DB_HOST: MySQL host.
        DB_PORT: MySQL port.
        DB_USER: MySQL username.
        DB_PASSWORD: MySQL password.
        DB_NAME: MySQL database name.
        SECRET_KEY: JWT signing secret – change in production!
        ALGORITHM: JWT algorithm (default HS256).
        ACCESS_TOKEN_EXPIRE_MINUTES: JWT TTL in minutes (default 7 days).
        RAZORPAY_KEY_ID: Razorpay API key ID.
        RAZORPAY_KEY_SECRET: Razorpay API key secret.
        APP_URL: Public API base URL.
        UPLOAD_DIR: Local directory for uploaded files.
        FRONTEND_URL: Frontend base URL (used in CORS).

        SMTP_HOST: SMTP server hostname (e.g. smtp.gmail.com).
        SMTP_PORT: SMTP server port (587 for STARTTLS, 465 for SSL).
        SMTP_USER: SMTP login username / sender address.
        SMTP_PASSWORD: SMTP login password or app password.
        FROM_EMAIL: Sender email shown to recipients (defaults to SMTP_USER).
        FROM_NAME: Sender display name shown in email clients.

        FAST2SMS_API_KEY: Fast2SMS API key for transactional SMS (India).
        WAREHOUSE_LAT: Latitude of the store / warehouse (for delivery ETA calculation).
        WAREHOUSE_LNG: Longitude of the store / warehouse.
    """

    PORT: int = 8000
    DEBUG: bool = True
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "hg77"
    DB_NAME: str = "medkart"
    SECRET_KEY: str = "change_me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    APP_URL: str = "http://localhost:8000"
    UPLOAD_DIR: str = "./public/uploads"
    FRONTEND_URL: str = "http://localhost:5173"

    # ── Email (SMTP) ──────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = ""           # defaults to SMTP_USER if blank
    FROM_NAME: str = "MathuraPharmeasy"

    # ── SMS (Fast2SMS — India) ────────────────────────────────────
    FAST2SMS_API_KEY: str = ""

    # ── Warehouse / Store location (used for delivery ETA) ───────
    # Default: Mathura, Uttar Pradesh (27.4924° N, 77.6737° E)
    WAREHOUSE_LAT: float = 27.4924
    WAREHOUSE_LNG: float = 77.6737

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance.

    Returns:
        Settings: Application settings loaded from env / .env.
    """
    return Settings()
