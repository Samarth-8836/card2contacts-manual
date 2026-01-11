from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application-wide configuration - SINGLE SOURCE OF TRUTH

    All production-ready settings are centralized here.
    Change these values in .env file for different environments.
    """

    # ==========================================
    # DEPLOYMENT & ENVIRONMENT
    # ==========================================
    ENVIRONMENT: str = "production"  # Options: "development", "staging", "production"
    FRONTEND_URL: str = "https://app.card2contacts.com"  # Default production URL
    BACKEND_URL: str = "https://app.card2contacts.com"  # Default production URL

    # CORS Origins - restrict in production for security
    ALLOWED_ORIGINS: str = "https://app.card2contacts.com"  # Default to production domain

    # ==========================================
    # DATABASE
    # ==========================================
    DATABASE_URL: str = "postgresql://admin:securepassword@localhost:5432/scanner_prod"

    # Database Connection Pool Settings
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600

    # ==========================================
    # AUTHENTICATION & SECURITY
    # ==========================================
    SECRET_KEY: str = "CHANGE_THIS_IN_PROD_TO_A_LONG_RANDOM_STRING"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days

    # ==========================================
    # GOOGLE OAUTH
    # ==========================================
    GOOGLE_CLIENT_ID: str = ""  # Required - set in .env
    GOOGLE_CLIENT_SECRET: str = ""  # Required - set in .env
    REDIRECT_URI: str = "https://app.card2contacts.com/api/auth/google/callback"  # Default production URL

    # ==========================================
    # AI/LLM CONFIGURATION - SINGLE PLACE TO CHANGE AI PROVIDER
    # ==========================================
    LLM_MODEL: str = "llama-3.1-8b-instant"
    # Options:
    #   GROQ MODELS (default provider - fast and affordable):
    #   - "llama-3.1-8b-instant" (fast, recommended)
    #   - "llama-3.3-70b-versatile" (more capable)
    #   - "openai/gpt-oss-20b" (Groq-hosted OpenAI model)
    #   - "openai/gpt-oss-120b" (larger variant)
    #   - groq/ prefix is optional, auto-added
    #
    #   GEMINI MODELS (Google AI):
    #   - "gemini/gemini-flash-lite-latest"
    #   - "gemini/gemini-pro"
    #
    # Note: All models use Groq unless they start with "gemini/"
    # Full list: https://console.groq.com/docs/models

    # AI Provider API Keys
    GEMINI_API_KEY: Optional[str] = None  # For Gemini models
    GROQ_API_KEY: Optional[str] = None     # For Groq models

    # ==========================================
    # OCR CONFIGURATION - SINGLE PLACE TO CHANGE PROVIDER
    # ==========================================
    OCR_PROVIDER: str = "mistral"  # Options: "mistral", "fallback"

    # Mistral OCR Settings (using official Mistral Python SDK)
    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_MODEL: str = "mistral-ocr-2512"
    # Options: "mistral-ocr-2512", "pixtral-12b-2409", "pixtral-large-latest"
    MISTRAL_TIMEOUT: int = 60

    # ==========================================
    # BUSINESS LOGIC - FREE TIER LIMITS
    # ==========================================
    FREE_TIER_SCAN_LIMIT: int = 4  # Number of scans allowed for unlicensed users

    # Enterprise License Limits (default values)
    DEFAULT_MAX_SUB_ACCOUNTS: int = 5  # Default sub-accounts for enterprise licenses

    # ==========================================
    # EMAIL CONFIGURATION (Future use)
    # ==========================================
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: Optional[str] = None

    # ==========================================
    # RATE LIMITING (Future use)
    # ==========================================
    RATE_LIMIT_PER_MINUTE: int = 60  # API requests per minute per user
    BULK_SCAN_MAX_FILES: int = 100   # Maximum files in a single bulk scan

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = "ignore"


# Global settings instance
settings = Settings()
