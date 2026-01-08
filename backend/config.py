from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application-wide configuration"""

    # Database
    DATABASE_URL: str = "postgresql://admin:securepassword@localhost:5432/scanner_prod"

    # Authentication
    SECRET_KEY: str = "CHANGE_THIS_IN_PROD_TO_A_LONG_RANDOM_STRING"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200

    # Google OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    REDIRECT_URI: str = "https://192.168.29.234.sslip.io:8000/api/auth/google/callback"

    # AI/LLM Configuration - SINGLE PLACE TO CHANGE AI PROVIDER
    LLM_MODEL: str = "groq/llama-3.1-8b-instant"  # Options: "groq/llama-3.1-8b-instant", "gemini/gemini-flash-lite-latest", etc.

    # AI Provider API Keys
    GEMINI_API_KEY: Optional[str] = None  # For Gemini models
    GROQ_API_KEY: Optional[str] = None     # For Groq models

    # OCR Configuration - SINGLE PLACE TO CHANGE PROVIDER
    OCR_PROVIDER: str = "mistral"  # Options: "mistral", "fallback"

    # Mistral OCR Settings (using official Mistral Python SDK)
    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_MODEL: str = "mistral-ocr-2512"  # Configurable: mistral-ocr-2512, pixtral-12b-2409, pixtral-large-latest, etc.
    MISTRAL_TIMEOUT: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = True


# Global settings instance
settings = Settings()
