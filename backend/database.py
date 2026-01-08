from typing import Optional
from datetime import datetime, timedelta
from sqlmodel import Field, SQLModel, create_engine, Session, select
from passlib.context import CryptContext
from backend.config import settings

# ==============================================================================
# 1. Database Setup
# ==============================================================================
# Use centralized DATABASE_URL from settings
engine = create_engine(settings.DATABASE_URL)

# ==============================================================================
# 2. Password Hashing
# ==============================================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ==============================================================================
# 3. Database Models
# ==============================================================================

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    # SINGLE-DEVICE ENFORCEMENT: Stores the current active session ID.
    # When user logs in, this is set to a new UUID. If it doesn't match the JWT's sid, session is invalid.
    current_session_id: Optional[str] = Field(default=None)

    # --- MIGRATION FLAGS ---
    requires_password_change: bool = Field(default=False)  # Distributor-created accounts must change password

    # --- LICENSE FIELDS ---
    license_id: Optional[int] = Field(default=None, foreign_key="license.id")  # For single-user licenses
    scan_count: int = Field(default=0)  # Tracks scans for unlicensed users (max 4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # --- DISTRIBUTOR TRACKING ---
    created_by_distributor_id: Optional[int] = Field(default=None, foreign_key="distributor.id")  # Tracks which distributor created this account

    # --- GOOGLE INTEGRATION FIELDS ---
    google_connected: bool = Field(default=False)
    google_spreadsheet_id: Optional[str] = Field(default=None)
    # Tokens (In prod, these should be encrypted at rest)
    google_access_token: Optional[str] = Field(default=None)
    google_refresh_token: Optional[str] = Field(default=None)
    google_token_uri: Optional[str] = Field(default="https://oauth2.googleapis.com/token")
    google_client_id: Optional[str] = Field(default=None)
    google_client_secret: Optional[str] = Field(default=None)
    email_feature_enabled: bool = Field(default=False)

# ------------------------------------------------------------------------------
# Enterprise Licensing Models
# ------------------------------------------------------------------------------

class License(SQLModel, table=True):
    """License holds the enterprise license key and usage limits."""
    id: Optional[int] = Field(default=None, primary_key=True)
    license_key: str = Field(index=True, unique=True)
    license_type: str = Field(default="enterprise")  # "single" or "enterprise"
    limits: str = Field(default='{"max_sub_accounts": 5}')  # JSON string (only for enterprise licenses)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class EnterpriseAdmin(SQLModel, table=True):
    """Enterprise admin account linked to a license."""
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    license_id: int = Field(foreign_key="license.id")
    # SINGLE-DEVICE ENFORCEMENT: Stores the current active session ID.
    # When admin logs in, this is set to a new UUID. If it doesn't match the JWT's sid, session is invalid.
    current_session_id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # --- MIGRATION FLAGS ---
    requires_password_change: bool = Field(default=False)  # Distributor-created accounts must change password

    # --- DISTRIBUTOR TRACKING ---
    created_by_distributor_id: Optional[int] = Field(default=None, foreign_key="distributor.id")  # Tracks which distributor created this account

    # --- GOOGLE INTEGRATION FIELDS (for admin's own scanning) ---
    google_connected: bool = Field(default=False)
    google_spreadsheet_id: Optional[str] = Field(default=None)
    google_access_token: Optional[str] = Field(default=None)
    google_refresh_token: Optional[str] = Field(default=None)
    google_token_uri: Optional[str] = Field(default="https://oauth2.googleapis.com/token")
    google_client_id: Optional[str] = Field(default=None)
    google_client_secret: Optional[str] = Field(default=None)
    email_feature_enabled: bool = Field(default=False)

class SubAccount(SQLModel, table=True):
    """Sub-account under an enterprise admin, limited scanning access."""
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)  # For sub-accounts, this stores username as email string
    password_hash: str
    admin_id: int = Field(foreign_key="enterpriseadmin.id")
    is_active: bool = Field(default=True)
    # SINGLE-DEVICE ENFORCEMENT: Stores the current active session ID.
    # When sub-account logs in, this is set to a new UUID. If it doesn't match the JWT's sid, session is invalid.
    current_session_id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # ENTERPRISE FEATURES: Sub-account has their own sheet within admin's spreadsheet
    # Sheet name format: "SubAccount_{email}"
    sheet_name: Optional[str] = Field(default=None)

    # Email template assignment: Template ID (row_id) from admin's Email_Templates sheet
    # If None, auto-emailing is disabled for this sub-account
    assigned_template_id: Optional[str] = Field(default=None)

# ------------------------------------------------------------------------------
# Distributor Models
# ------------------------------------------------------------------------------

class Distributor(SQLModel, table=True):
    """Distributor role assignment - can be attached to any user type."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int  # ID of the user (User, EnterpriseAdmin, or SubAccount)
    user_type: str  # "single", "enterprise_admin", or "sub_account"
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class DistributorLicense(SQLModel, table=True):
    """Tracks licenses owned and assigned by distributors."""
    id: Optional[int] = Field(default=None, primary_key=True)
    distributor_id: int = Field(foreign_key="distributor.id")
    license_id: int = Field(foreign_key="license.id")
    license_type: str  # "single" or "enterprise" (denormalized for quick queries)
    is_assigned: bool = Field(default=False)
    assigned_to_user_id: Optional[int] = Field(default=None)  # ID of assigned user
    assigned_to_user_type: Optional[str] = Field(default=None)  # "single" or "enterprise_admin"
    assigned_at: Optional[datetime] = Field(default=None)
    purchased_at: datetime = Field(default_factory=datetime.utcnow)

class DistributorPurchase(SQLModel, table=True):
    """Tracks distributor license purchase history."""
    id: Optional[int] = Field(default=None, primary_key=True)
    distributor_id: int = Field(foreign_key="distributor.id")
    license_type: str  # "single" or "enterprise"
    count: int  # Number of licenses purchased
    purchased_at: datetime = Field(default_factory=datetime.utcnow)

# ------------------------------------------------------------------------------
# App Owner / Developer Models
# ------------------------------------------------------------------------------

class AppOwner(SQLModel, table=True):
    """App owner/developer account with full system access for monitoring."""
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    full_name: str
    is_active: bool = Field(default=True)
    current_session_id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = Field(default=None)

# ------------------------------------------------------------------------------
# OTP Authentication Models
# ------------------------------------------------------------------------------

class OTPRecord(SQLModel, table=True):
    """Stores OTP codes for login verification."""
    id: Optional[int] = Field(default=None, primary_key=True)
    identifier: str = Field(index=True)  # email or username used to login
    user_type: str  # "single", "enterprise_admin", "sub_account"
    user_id: int  # actual user ID for reference
    otp_code: str  # 6-digit code
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    is_used: bool = Field(default=False)
    attempts: int = Field(default=0)  # Track OTP verification attempts (max 5)
    pending_session_id: str  # UUID for tracking this login attempt

# ==============================================================================
# 4. Utilities
# ==============================================================================

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def is_license_valid(license: Optional[License]) -> bool:
    """
    Check if a license is valid.
    A license is valid if:
    1. It exists
    2. It is active
    3. It was created within the last 1 year
    """
    if not license:
        return False

    if not license.is_active:
        return False

    # Check if license is older than 1 year
    one_year_ago = datetime.utcnow() - timedelta(days=365)
    if license.created_at < one_year_ago:
        return False

    return True