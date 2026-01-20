from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Request,
    BackgroundTasks,
)
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import JWTError, jwt
import uuid
import httpx
import json
import base64
import os
import io
import asyncio
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# AI Imports
from litellm import acompletion, completion

# Allow non-HTTPS for OAuth dev environment
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

# Configuration and OCR imports
from backend.config import settings
from backend.ocr import get_ocr_service, initialize_ocr_service

from backend.database import (
    create_db_and_tables,
    get_session,
    User,
    verify_password,
    get_password_hash,
    License,
    EnterpriseAdmin,
    SubAccount,
    Distributor,
    DistributorLicense,
    DistributorPurchase,
    OTPRecord,
    AppOwner,
    is_license_valid,
    safe_commit,
)
from backend.email_utils import (
    send_otp_email,
    send_password_reset_email,
    send_account_credentials_email,
    send_sub_account_otp_email,
    send_distributor_contact_request_email,
    generate_otp,
    generate_random_password,
    mask_email,
)
from sqlmodel import or_
from backend.google_utils import (
    append_to_sheet,
    get_google_creds,
    create_spreadsheet_in_folder,
    fetch_templates,
    add_template,
    set_active_template,
    update_template_content,
    send_gmail,
    get_template_attachments,
    stage_bulk_image,
    stage_bulk_image_sub_account,
    check_staging_count_for_user,
    submit_bulk_session,
    submit_bulk_session_sub_account,
    clear_staging_data,
    clear_staging_data_sub_account,
    check_staging_count,
    process_bulk_queue_sync,
    handle_google_api_error,
    verify_connection_health,
    ensure_creds,
    create_sub_account_sheet,
    append_to_sub_account_sheet,
    export_sheet_as_excel,
    export_combined_contacts,
    check_granted_scopes,
)

app = FastAPI()

# ==========================================
# 1. CONFIGURATION
# ==========================================
# Configuration now loaded from backend/config.py and .env file
# Access via: settings.SECRET_KEY, settings.GEMINI_API_KEY, etc.

# Set environment variables for AI providers (required by LiteLLM)
if settings.GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
if settings.GROQ_API_KEY:
    os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY

# Set environment variables for Google OAuth (required by google-auth-oauthlib)
os.environ["GOOGLE_CLIENT_ID"] = settings.GOOGLE_CLIENT_ID
os.environ["GOOGLE_CLIENT_SECRET"] = settings.GOOGLE_CLIENT_SECRET

GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

# VCard Schema
VCF_SCHEMA = {
    "type": "object",
    "properties": {
        "fn": {"type": "array", "items": {"type": "string"}},
        "org": {"type": ["string", "null"]},
        "title": {"type": ["string", "null"]},
        "tel": {"type": "array", "items": {"type": "string"}},
        "email": {"type": "array", "items": {"type": "string"}},
        "url": {"type": "array", "items": {"type": "string"}},
        "adr": {"type": "array", "items": {"type": "string"}},
        "cat": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific business category e.g. Plumbing, Legal, Software, Forex Trading",
        },
        "notes": {"type": ["string", "null"]},
    },
    "required": ["fn"],
}

# Parse CORS origins from settings (comma-separated string to list)
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()

    # Initialize OCR service (using official Mistral SDK)
    provider_configs = {
        "mistral": {
            "api_key": settings.MISTRAL_API_KEY,
            "model": settings.MISTRAL_MODEL,
            "timeout": settings.MISTRAL_TIMEOUT,
        },
        "fallback": {},
    }

    config = provider_configs.get(settings.OCR_PROVIDER, {})
    initialize_ocr_service(settings.OCR_PROVIDER, config)
    print(f"✅ OCR Service Initialized: {settings.OCR_PROVIDER}")


# ==========================================
# 2. DATA MODELS
# ==========================================
class UserLogin(BaseModel):
    email: str  # Can be email (single user) or username (enterprise)
    password: str


class UserCreate(BaseModel):
    email: str
    password: str


# --- OTP Authentication Models ---
class LoginInitiateRequest(BaseModel):
    identifier: str  # Email for all user types
    password: str


class LoginInitiateResponse(BaseModel):
    status: str  # "otp_sent", "password_change_required", "error"
    user_type: str = None
    otp_sent_to: str = None  # Masked email
    session_token: str = None  # UUID to track this login attempt
    message: str = None


class OTPVerifyRequest(BaseModel):
    session_token: str
    otp_code: str


class PasswordResetRequest(BaseModel):
    email: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ContactSave(BaseModel):
    fn: list = []
    org: str = ""
    title: str = ""
    tel: list = []
    email: list = []
    url: list = []
    adr: list = []
    cat: list = []  # Added Business Category
    notes: str = ""


class TemplateCreate(BaseModel):
    subject: str
    body: str
    attachments: list[dict] = (
        None  # List of {filename: str, data: str (base64), size: int}, max 20MB total
    )


class SubAccountCreate(BaseModel):
    email: str  # For sub-accounts, this is treated as username string
    password: str


class SubAccountUpdate(BaseModel):
    email: str = None  # For sub-accounts, this is treated as username string
    password: str = None


class DistributorPurchaseRequest(BaseModel):
    license_type: str  # "single" or "enterprise"
    count: int
    max_sub_accounts: int = 1  # Only for enterprise licenses


class DistributorAccountCreate(BaseModel):
    account_type: str  # "single" or "enterprise"
    email: str  # Required for all users
    password: str = None  # Optional - auto-generated if not provided
    upgrade_from_email: str = (
        None  # Optional - email of unlicensed account to upgrade/replace
    )


class SeatExpansionRequest(BaseModel):
    additional_seats: int  # Number of seats to add to current license


class AppOwnerLogin(BaseModel):
    email: str
    password: str


class DistributorPromoteRequest(BaseModel):
    email: str
    user_type: str  # "single", "enterprise_admin", or "sub_account"


class DistributorRevokeRequest(BaseModel):
    email: str
    user_type: str  # "single", "enterprise_admin", or "sub_account"


# ==========================================
# 3. AUTHENTICATION HELPERS & ENDPOINTS
# ==========================================


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_current_user_multi(token: str, db: Session):
    """
    Extended user lookup supporting all user types.
    Returns tuple: (user_object, user_type)
    user_type is one of: 'single', 'enterprise_admin', 'sub_account'

    SINGLE-DEVICE ENFORCEMENT - SESSION VALIDATION:
    This function validates that the session ID (sid) in the JWT token matches
    the current_session_id stored in the database. If they don't match, it means:
    1. The user logged in on another device (which created a new session_id)
    2. The admin deactivated the account
    3. The user changed their password

    In all cases, this validation ensures only ONE active session per account.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        identifier = payload.get("sub")  # This is always an email now
        sid = payload.get("sid")
        user_type = payload.get("type", "single")

        if not identifier or not sid:
            raise HTTPException(status_code=401, detail="Invalid token")

        if user_type == "enterprise_admin":
            statement = select(EnterpriseAdmin).where(
                EnterpriseAdmin.email == identifier
            )
            user = db.exec(statement).first()
        elif user_type == "sub_account":
            statement = select(SubAccount).where(SubAccount.email == identifier)
            user = db.exec(statement).first()
            if user and not user.is_active:
                raise HTTPException(status_code=403, detail="Account deactivated")
        else:  # single user
            statement = select(User).where(User.email == identifier)
            user = db.exec(statement).first()

        # CRITICAL CHECK: Validate session ID matches
        if not user or user.current_session_id != sid:
            raise HTTPException(status_code=401, detail="Session expired")

        return user, user_type
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


def get_current_user(token: str, db: Session):
    """Backward compatible - returns just the user object (for existing endpoints)."""
    user, user_type = get_current_user_multi(token, db)
    return user


def get_current_admin(token: str, db: Session):
    """Get current user, must be enterprise admin."""
    user, user_type = get_current_user_multi(token, db)
    if user_type != "enterprise_admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def get_current_distributor(token: str, db: Session):
    """Get current user and verify they have distributor role."""
    user, user_type = get_current_user_multi(token, db)

    # Check if user has distributor role
    stmt = select(Distributor).where(
        Distributor.user_id == user.id,
        Distributor.user_type == user_type,
        Distributor.is_active == True,
    )
    distributor = db.exec(stmt).first()

    if not distributor:
        raise HTTPException(status_code=403, detail="Distributor access required")

    return user, user_type, distributor


def get_current_app_owner(token: str, db: Session):
    """Get current app owner and verify authentication."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email = payload.get("sub")
        sid = payload.get("sid")
        user_type = payload.get("type")

        if not email or not sid or user_type != "app_owner":
            raise HTTPException(status_code=401, detail="Invalid token")

        statement = select(AppOwner).where(AppOwner.email == email)
        app_owner = db.exec(statement).first()

        # CRITICAL CHECK: Validate session ID matches and account is active
        if (
            not app_owner
            or app_owner.current_session_id != sid
            or not app_owner.is_active
        ):
            raise HTTPException(
                status_code=401, detail="Session expired or account inactive"
            )

        return app_owner
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")


def is_google_connected(user, user_type: str, db: Session) -> bool:
    """
    Check if Google is connected for any user type.
    For sub-accounts, checks if their admin has Google connected.
    """
    if user_type == "sub_account":
        admin_stmt = select(EnterpriseAdmin).where(EnterpriseAdmin.id == user.admin_id)
        admin = db.exec(admin_stmt).first()
        return admin.google_connected if admin else False
    else:
        return user.google_connected


def get_admin_for_user(user, user_type: str, db: Session):
    """
    Get the admin for a user.
    - For sub_account: returns their admin
    - For enterprise_admin: returns themselves
    - For single user: returns themselves
    """
    if user_type == "sub_account":
        admin_stmt = select(EnterpriseAdmin).where(EnterpriseAdmin.id == user.admin_id)
        return db.exec(admin_stmt).first()
    else:
        return user


def get_google_creds_for_user(user, user_type: str, db: Session):
    """
    Get Google credentials for any user type.
    For sub-accounts, gets the admin's credentials.
    Returns credentials or None.
    """
    from backend.google_utils import get_google_creds

    if user_type == "sub_account":
        admin_stmt = select(EnterpriseAdmin).where(EnterpriseAdmin.id == user.admin_id)
        admin = db.exec(admin_stmt).first()
        if not admin:
            return None
        return get_google_creds(admin, db)
    else:
        return get_google_creds(user, db)


def get_spreadsheet_id_for_user(user, user_type: str, db: Session):
    """
    Get Google spreadsheet ID for any user type.
    For sub-accounts, gets the admin's spreadsheet ID.
    Returns spreadsheet_id or None.
    """
    if user_type == "sub_account":
        admin_stmt = select(EnterpriseAdmin).where(EnterpriseAdmin.id == user.admin_id)
        admin = db.exec(admin_stmt).first()
        if not admin:
            return None
        return admin.google_spreadsheet_id
    else:
        return user.google_spreadsheet_id


@app.post("/api/register")
def register(user_data: UserCreate, db: Session = Depends(get_session)):
    # Check email uniqueness across ALL user types
    # 1. Check User.email
    email_check = select(User).where(User.email == user_data.email)
    if db.exec(email_check).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # 2. Check EnterpriseAdmin.email
    admin_check = select(EnterpriseAdmin).where(
        EnterpriseAdmin.email == user_data.email
    )
    if db.exec(admin_check).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # 3. Check SubAccount.email
    sub_check = select(SubAccount).where(SubAccount.email == user_data.email)
    if db.exec(sub_check).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        requires_password_change=False,
        license_id=None,  # Self-registered users don't get a license
        scan_count=0,
    )
    db.add(new_user)
    db.commit()
    return {
        "message": "Account created successfully",
        "account_type": "unlicensed",
        "notice": f"You have registered with an unlicensed account. You can scan up to {settings.FREE_TIER_SCAN_LIMIT} business cards. To scan more cards and unlock full features, please contact a distributor to upgrade to a licensed account.",
    }


@app.post("/api/check-status")
def check_user_status(user_data: UserLogin, db: Session = Depends(get_session)):
    """
    Check if user has an active session on another device.

    This endpoint is called BEFORE login to detect active sessions and warn the user.
    Returns:
        - status: "active" if user has current_session_id (logged in elsewhere)
        - status: "inactive" if user can login without invalidating another session

    Part of the single-device enforcement system that prevents multiple concurrent logins.
    """
    # Try single user first (by email)
    statement = select(User).where(User.email == user_data.email)
    user = db.exec(statement).first()
    if user and verify_password(user_data.password, user.password_hash):
        if user.current_session_id:
            return {"status": "active", "message": "User is currently logged in."}
        return {"status": "inactive", "message": "Ready to login."}

    # Try enterprise admin (by email)
    admin_stmt = select(EnterpriseAdmin).where(EnterpriseAdmin.email == user_data.email)
    admin = db.exec(admin_stmt).first()
    if admin and verify_password(user_data.password, admin.password_hash):
        if admin.current_session_id:
            return {"status": "active", "message": "Admin is currently logged in."}
        return {"status": "inactive", "message": "Ready to login."}

    # Try sub-account (by email)
    sub_stmt = select(SubAccount).where(SubAccount.email == user_data.email)
    sub = db.exec(sub_stmt).first()
    if sub and verify_password(user_data.password, sub.password_hash):
        if not sub.is_active:
            raise HTTPException(status_code=403, detail="Account deactivated")
        if sub.current_session_id:
            return {"status": "active", "message": "User is currently logged in."}
        return {"status": "inactive", "message": "Ready to login."}

    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/api/login")
def login(user_data: UserLogin, db: Session = Depends(get_session)):
    """
    DEPRECATED: Use /api/login/initiate for OTP-based login.
    This endpoint is kept for backward compatibility during transition.

    Unified login endpoint for all user types.
    """
    session_id = str(uuid.uuid4())

    # Try single user first (by email)
    statement = select(User).where(User.email == user_data.email)
    user = db.exec(statement).first()
    if user and verify_password(user_data.password, user.password_hash):
        user.current_session_id = session_id
        db.add(user)
        db.commit()
        identifier = user.email  # Use email as identifier for JWT
        access_token = create_access_token(
            data={"sub": identifier, "sid": session_id, "type": "single"}
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_type": "single",
        }

    # Try enterprise admin (by email)
    admin_stmt = select(EnterpriseAdmin).where(EnterpriseAdmin.email == user_data.email)
    admin = db.exec(admin_stmt).first()
    if admin and verify_password(user_data.password, admin.password_hash):
        admin.current_session_id = session_id
        db.add(admin)
        db.commit()
        access_token = create_access_token(
            data={"sub": admin.email, "sid": session_id, "type": "enterprise_admin"}
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_type": "enterprise_admin",
        }

    # Try sub-account (by email)
    sub_stmt = select(SubAccount).where(SubAccount.email == user_data.email)
    sub = db.exec(sub_stmt).first()
    if sub and verify_password(user_data.password, sub.password_hash):
        if not sub.is_active:
            raise HTTPException(
                status_code=403, detail="Account deactivated by administrator"
            )
        sub.current_session_id = session_id
        db.add(sub)
        db.commit()
        access_token = create_access_token(
            data={"sub": sub.email, "sid": session_id, "type": "sub_account"}
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_type": "sub_account",
        }

    raise HTTPException(status_code=401, detail="Invalid credentials")


# ==========================================
# APP OWNER LOGIN ENDPOINT
# ==========================================


@app.post("/api/admin/login")
def app_owner_login(login_data: AppOwnerLogin, db: Session = Depends(get_session)):
    """
    App owner/developer login endpoint.
    Returns JWT token for accessing admin endpoints.
    """
    session_id = str(uuid.uuid4())

    # Find app owner by email
    statement = select(AppOwner).where(AppOwner.email == login_data.email)
    app_owner = db.exec(statement).first()

    if not app_owner:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    if not verify_password(login_data.password, app_owner.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if account is active
    if not app_owner.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    # Update session and last login
    app_owner.current_session_id = session_id
    app_owner.last_login = datetime.utcnow()
    db.add(app_owner)
    db.commit()

    # Create JWT token
    access_token = create_access_token(
        data={"sub": app_owner.email, "sid": session_id, "type": "app_owner"}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": "app_owner",
        "full_name": app_owner.full_name,
    }


# ==========================================
# OTP-BASED LOGIN FLOW ENDPOINTS
# ==========================================

OTP_EXPIRY_MINUTES = 5
MAX_OTP_ATTEMPTS = 5


def _find_user_by_identifier(identifier: str, db: Session):
    """
    Find user by email identifier.
    Returns tuple: (user_object, user_type, email_for_otp)
    """
    # Try single user first (by email)
    statement = select(User).where(User.email == identifier)
    user = db.exec(statement).first()
    if user:
        return user, "single", user.email

    # Try enterprise admin (by email)
    admin_stmt = select(EnterpriseAdmin).where(EnterpriseAdmin.email == identifier)
    admin = db.exec(admin_stmt).first()
    if admin:
        return admin, "enterprise_admin", admin.email

    # Try sub-account (by email - which is username string for sub-accounts)
    sub_stmt = select(SubAccount).where(SubAccount.email == identifier)
    sub = db.exec(sub_stmt).first()
    if sub:
        # Get admin's email for sub-account OTP
        admin_stmt = select(EnterpriseAdmin).where(EnterpriseAdmin.id == sub.admin_id)
        admin = db.exec(admin_stmt).first()
        return sub, "sub_account", admin.email if admin else None

    return None, None, None


@app.post("/api/login/initiate")
def login_initiate(data: LoginInitiateRequest, db: Session = Depends(get_session)):
    """
    Step 1 of OTP login: Verify credentials and send OTP.

    Flow:
    1. Find user by email identifier
    2. Verify password
    3. Generate OTP and send to appropriate email
    4. Return session token for OTP verification
    """
    user, user_type, email_for_otp = _find_user_by_identifier(data.identifier, db)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if sub-account is active
    if user_type == "sub_account" and not user.is_active:
        raise HTTPException(
            status_code=403, detail="Account deactivated by administrator"
        )

    # Generate session token for tracking this login attempt
    session_token = str(uuid.uuid4())

    # Check if email is available for OTP
    if not email_for_otp:
        if user_type == "sub_account":
            raise HTTPException(
                status_code=400,
                detail="Admin's email not configured. Contact your administrator.",
            )
        else:
            raise HTTPException(
                status_code=400, detail="Email not configured for OTP delivery"
            )

    # Generate and send OTP
    otp_code = generate_otp()

    # Create OTP record
    otp_record = OTPRecord(
        identifier=data.identifier,
        user_type=user_type,
        user_id=user.id,
        otp_code=otp_code,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES),
        pending_session_id=session_token,
    )
    db.add(otp_record)
    db.commit()

    # Send OTP email
    if user_type == "sub_account":
        # Send to admin with sub-account info (user.email is the username string for sub-accounts)
        send_sub_account_otp_email(email_for_otp, user.email, otp_code)
    else:
        send_otp_email(email_for_otp, otp_code)

    # Check if password change is required (for distributor-created accounts)
    requires_password_change = getattr(user, "requires_password_change", False)

    return {
        "status": "otp_sent",
        "user_type": user_type,
        "otp_sent_to": mask_email(email_for_otp),
        "session_token": session_token,
        "requires_password_change": requires_password_change,
        "message": f"Verification code sent to {mask_email(email_for_otp)}",
    }


@app.post("/api/login/verify-otp")
def login_verify_otp(data: OTPVerifyRequest, db: Session = Depends(get_session)):
    """
    Step 2 of OTP login: Verify OTP and complete login.
    """
    # Find OTP record
    otp_stmt = select(OTPRecord).where(
        OTPRecord.pending_session_id == data.session_token, OTPRecord.is_used == False
    )
    otp_record = db.exec(otp_stmt).first()

    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid or expired session")

    # Check if OTP is expired
    if datetime.utcnow() > otp_record.expires_at:
        raise HTTPException(
            status_code=400, detail="Verification code expired. Please try again."
        )

    # Check attempts
    if otp_record.attempts >= MAX_OTP_ATTEMPTS:
        otp_record.is_used = True
        db.add(otp_record)
        db.commit()
        raise HTTPException(
            status_code=400, detail="Too many attempts. Please try again."
        )

    # Verify OTP code
    if otp_record.otp_code != data.otp_code:
        otp_record.attempts += 1
        db.add(otp_record)
        db.commit()
        remaining = MAX_OTP_ATTEMPTS - otp_record.attempts
        raise HTTPException(
            status_code=400, detail=f"Invalid code. {remaining} attempts remaining."
        )

    # Find the user first (before modifying OTP record)
    user, user_type, _ = _find_user_by_identifier(otp_record.identifier, db)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    # Mark OTP as used
    otp_record.is_used = True

    # Create new session and update user
    session_id = str(uuid.uuid4())
    user.current_session_id = session_id

    # Commit both changes
    db.commit()

    # Refresh user to ensure we have the committed state
    db.refresh(user)

    # Get identifier for JWT - always use email now
    identifier = user.email

    # Check if password change is required
    requires_password_change = getattr(user, "requires_password_change", False)

    access_token = create_access_token(
        data={"sub": identifier, "sid": session_id, "type": user_type}
    )

    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "user_type": user_type,
        "requires_password_change": requires_password_change,
    }


@app.post("/api/login/resend-otp")
def login_resend_otp(session_token: str, db: Session = Depends(get_session)):
    """
    Resend OTP for an existing login session.
    """
    # Find the pending OTP record
    otp_stmt = select(OTPRecord).where(
        OTPRecord.pending_session_id == session_token, OTPRecord.is_used == False
    )
    otp_record = db.exec(otp_stmt).first()

    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid session")

    # Check if it's a migration/setup record
    if otp_record.otp_code in ["MIGRATION", "EMAIL_SETUP"]:
        raise HTTPException(
            status_code=400, detail="Complete setup first before requesting OTP"
        )

    # Find user and email
    user, user_type, email_for_otp = _find_user_by_identifier(otp_record.identifier, db)
    if not user or not email_for_otp:
        raise HTTPException(
            status_code=400, detail="Could not find email for OTP delivery"
        )

    # Generate new OTP
    new_otp_code = generate_otp()

    # Update existing record
    otp_record.otp_code = new_otp_code
    otp_record.created_at = datetime.utcnow()
    otp_record.expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    otp_record.attempts = 0
    db.add(otp_record)
    db.commit()

    # Send OTP email
    if user_type == "sub_account":
        send_sub_account_otp_email(email_for_otp, user.username, new_otp_code)
    else:
        send_otp_email(email_for_otp, new_otp_code)

    return {
        "status": "otp_sent",
        "otp_sent_to": mask_email(email_for_otp),
        "message": f"New verification code sent to {mask_email(email_for_otp)}",
    }


# ==========================================
# PASSWORD MANAGEMENT ENDPOINTS
# ==========================================


@app.post("/api/password/reset-request")
def password_reset_request(
    data: PasswordResetRequest, db: Session = Depends(get_session)
):
    """
    Request password reset. Sends new password to email.
    Only available for single users and enterprise admins (not sub-accounts).
    """
    # Try to find user by email
    user = None
    user_type = None

    # Check single users
    user_stmt = select(User).where(User.email == data.email)
    user = db.exec(user_stmt).first()
    if user:
        user_type = "single"

    # Check enterprise admins
    if not user:
        admin_stmt = select(EnterpriseAdmin).where(
            EnterpriseAdmin.admin_email == data.email
        )
        user = db.exec(admin_stmt).first()
        if user:
            user_type = "enterprise_admin"

    # Always return success to prevent email enumeration
    if not user:
        return {
            "status": "success",
            "message": "If this email is registered, a new password has been sent.",
        }

    # Generate new random password
    new_password = generate_random_password(12)
    user.password_hash = get_password_hash(new_password)
    user.requires_password_change = True  # Force password change on next login

    # Invalidate current session
    user.current_session_id = None

    db.add(user)
    db.commit()

    # Send email with new password
    send_password_reset_email(data.email, new_password)

    return {
        "status": "success",
        "message": "If this email is registered, a new password has been sent.",
    }


@app.post("/api/user/change-password")
def change_password(
    data: ChangePasswordRequest, token: str, db: Session = Depends(get_session)
):
    """
    Change password for authenticated user.
    """
    user, user_type = get_current_user_multi(token, db)

    # Verify current password
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Validate new password (minimum 6 characters)
    if len(data.new_password) < 6:
        raise HTTPException(
            status_code=400, detail="New password must be at least 6 characters"
        )

    # Update password
    user.password_hash = get_password_hash(data.new_password)
    user.requires_password_change = False

    # Invalidate session to force re-login
    user.current_session_id = None

    db.add(user)
    db.commit()

    return {
        "status": "success",
        "message": "Password changed successfully. Please login again.",
    }


@app.get("/api/me")
def get_user_info(token: str, db: Session = Depends(get_session)):
    user, user_type = get_current_user_multi(token, db)

    # Check if user has distributor role
    dist_stmt = select(Distributor).where(
        Distributor.user_id == user.id,
        Distributor.user_type == user_type,
        Distributor.is_active == True,
    )
    is_distributor = db.exec(dist_stmt).first() is not None

    if user_type == "single":
        # Check license status
        user_license = None
        license_status = "none"
        scans_remaining = None
        license_expires_at = None

        if user.license_id:
            license_stmt = select(License).where(License.id == user.license_id)
            user_license = db.exec(license_stmt).first()

            if user_license:
                if is_license_valid(user_license):
                    license_status = "valid"
                    scans_remaining = "unlimited"
                    license_expires_at = user_license.created_at + timedelta(days=365)
                else:
                    license_status = "expired"
                    scans_remaining = max(
                        0, settings.FREE_TIER_SCAN_LIMIT - user.scan_count
                    )
                    license_expires_at = user_license.created_at + timedelta(days=365)
        else:
            # No license - show remaining free scans
            scans_remaining = max(0, settings.FREE_TIER_SCAN_LIMIT - user.scan_count)

        # Check granted scopes
        scope_info = check_granted_scopes(user, db)

        return {
            "email": user.email,
            "status": "active",
            "user_type": "single",
            "google_linked": user.google_connected,  # Has tokens (linked at some point)
            "google_connected": user.google_connected
            and scope_info["has_all_scopes"],  # Has all required scopes
            "google_missing_scopes": scope_info["missing_scopes"],
            "is_distributor": is_distributor,
            "requires_password_change": user.requires_password_change,
            "license_status": license_status,
            "scans_remaining": scans_remaining,
            "scan_count": user.scan_count,
            "license_expires_at": license_expires_at.isoformat()
            if license_expires_at
            else None,
        }
    elif user_type == "enterprise_admin":
        # Check license status for enterprise admin
        admin_license = None
        license_status = "none"
        license_expires_at = None

        if user.license_id:
            license_stmt = select(License).where(License.id == user.license_id)
            admin_license = db.exec(license_stmt).first()

            if admin_license:
                if is_license_valid(admin_license):
                    license_status = "valid"
                    license_expires_at = admin_license.created_at + timedelta(days=365)
                else:
                    license_status = "expired"
                    license_expires_at = admin_license.created_at + timedelta(days=365)

        # Check granted scopes
        scope_info = check_granted_scopes(user, db)

        return {
            "email": user.email,
            "status": "active",
            "user_type": "enterprise_admin",
            "google_linked": user.google_connected,  # Has tokens (linked at some point)
            "google_connected": user.google_connected
            and scope_info["has_all_scopes"],  # Has all required scopes
            "google_missing_scopes": scope_info["missing_scopes"],
            "is_distributor": is_distributor,
            "requires_password_change": user.requires_password_change,
            "license_status": license_status,
            "license_expires_at": license_expires_at.isoformat()
            if license_expires_at
            else None,
        }
    else:  # sub_account
        # Sub-accounts inherit Google connection from their admin
        admin_stmt = select(EnterpriseAdmin).where(EnterpriseAdmin.id == user.admin_id)
        admin = db.exec(admin_stmt).first()

        # Check admin's granted scopes
        scope_info = {
            "has_all_scopes": False,
            "missing_scopes": ["Drive Access", "Gmail Access"],
        }
        admin_linked = False
        if admin:
            scope_info = check_granted_scopes(admin, db)
            admin_linked = admin.google_connected

        return {
            "email": user.email,  # For sub-accounts, this is the username string
            "status": "active",
            "user_type": "sub_account",
            "google_linked": admin_linked,  # Admin has tokens (linked at some point)
            "google_connected": admin_linked
            and scope_info["has_all_scopes"],  # Admin has all required scopes
            "google_missing_scopes": scope_info["missing_scopes"],
            "email_feature_enabled": user.assigned_template_id
            is not None,  # Email enabled if template assigned
            "is_distributor": is_distributor,
        }


@app.post("/api/logout")
def logout(token: str, db: Session = Depends(get_session)):
    try:
        user, user_type = get_current_user_multi(token, db)
        user.current_session_id = None
        db.add(user)
        db.commit()
    except:
        pass
    return {"message": "Logged out"}


@app.post("/api/user/request-upgrade")
def request_account_upgrade(token: str, db: Session = Depends(get_session)):
    """
    Request to upgrade from an unlicensed account to a licensed account.
    Returns information about how to contact a distributor.
    """
    user, user_type = get_current_user_multi(token, db)

    if user_type != "single":
        raise HTTPException(
            status_code=400, detail="Only single users can request upgrades"
        )

    # Check if user already has a valid license
    if user.license_id:
        license_stmt = select(License).where(License.id == user.license_id)
        user_license = db.exec(license_stmt).first()
        if is_license_valid(user_license):
            raise HTTPException(
                status_code=400, detail="You already have a valid license"
            )

    return {
        "status": "upgrade_requested",
        "message": "To upgrade your account to a licensed account, please contact a distributor. They will help you choose between a single-user license or an enterprise license, and create a new licensed account for you.",
        "instructions": [
            "Contact a distributor to request a license upgrade",
            "The distributor will ask if you need a single-user or enterprise license",
            "Your current unlicensed account will be replaced with a new licensed account",
            "All your data will be transferred to the new account",
        ],
        "current_account": {
            "email": user.email,
            "username": user.username,
            "scans_used": user.scan_count,
        },
    }


@app.post("/api/user/contact-distributor")
def contact_distributor_network(token: str, db: Session = Depends(get_session)):
    """
    Send a contact request email to the distributor network for license purchase callback.
    """
    user, user_type = get_current_user_multi(token, db)

    if user_type != "single":
        raise HTTPException(
            status_code=400, detail="Only single users can request distributor contact"
        )

    # Send email notification to distributor network
    email_sent = send_distributor_contact_request_email(user.email, user.username)

    if not email_sent:
        raise HTTPException(
            status_code=500,
            detail="Failed to send contact request. Please try again later.",
        )

    return {
        "status": "success",
        "message": "Your contact request has been sent to our distributor network. You will be contacted shortly to discuss your license requirements.",
    }


# ==========================================
# 4. GOOGLE OAUTH ENDPOINTS
# ==========================================


@app.get("/api/auth/google/login")
def login_with_google():
    client_config = {
        "web": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(
        client_config, scopes=GOOGLE_SCOPES, redirect_uri=settings.REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state="login_flow",
        prompt="consent",
    )
    return {"auth_url": auth_url}


@app.get("/api/auth/google/link")
def link_google_account(token: str, db: Session = Depends(get_session)):
    user, user_type = get_current_user_multi(token, db)

    # Sub-accounts cannot link Google - only their admin can
    if user_type == "sub_account":
        raise HTTPException(
            status_code=403,
            detail="Sub-accounts cannot link Google. Contact your administrator.",
        )

    client_config = {
        "web": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(
        client_config, scopes=GOOGLE_SCOPES, redirect_uri=settings.REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=token,
        prompt="consent",
    )
    return {"auth_url": auth_url}


@app.get("/api/auth/google/callback")
def google_callback(state: str, code: str, db: Session = Depends(get_session)):
    """
    Google OAuth callback handler.

    SINGLE-DEVICE ENFORCEMENT:
    Like the /api/login endpoint, this creates a NEW session_id and overwrites
    the existing current_session_id, automatically invalidating any previous session.

    Note: For Google OAuth, we cannot show a pre-login warning since the user's
    identity is only known after they complete OAuth. The session invalidation
    happens automatically on successful OAuth completion.

    PERMISSION VALIDATION:
    This endpoint validates that ALL required scopes are granted by the user.
    If any required permissions are missing, the linking is rejected and the user
    must re-authorize with complete permissions.
    """
    try:
        client_config = {
            "web": {
                "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        flow = Flow.from_client_config(
            client_config, scopes=GOOGLE_SCOPES, redirect_uri=settings.REDIRECT_URI
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        user = None

        # Validate that ALL required scopes are granted
        granted_scopes = (
            set(creds.scopes) if hasattr(creds, "scopes") and creds.scopes else set()
        )
        required_scopes = set(GOOGLE_SCOPES)
        missing_scopes = required_scopes - granted_scopes

        if missing_scopes:
            # User denied some permissions - redirect with error
            print(f"Incomplete permissions granted. Missing scopes: {missing_scopes}")
            return RedirectResponse(
                url=f"/?error=incomplete_permissions&missing={','.join(missing_scopes)}"
            )

        # Track if this is the first time linking Google account
        # (to show notification only once, not on every re-auth/refresh)
        is_first_time_linking = False

        if state == "login_flow":
            # New Google sign-up: must have all permissions granted upfront
            user_info_service = build("oauth2", "v2", credentials=creds)
            user_info = user_info_service.userinfo().get().execute()
            email = user_info.get("email")

            statement = select(User).where(User.email == email)
            user = db.exec(statement).first()
            user_type = "single"
            if not user:
                # Create new user with Google account - all permissions already validated above
                user = User(
                    email=email,
                    password_hash="GOOGLE_LINKED_ACCOUNT",
                    google_connected=True,  # Auto-link since signed up with Google
                )
                db.add(user)
                if not safe_commit(db):
                    raise HTTPException(status_code=500, detail="Failed to create user")
                db.refresh(user)
                is_first_time_linking = True  # First time signing up via Google
            else:
                # Existing user logging in via Google - check if already linked
                is_first_time_linking = not user.google_connected
        else:
            user, user_type = get_current_user_multi(state, db)
            # Existing logged-in user linking their Google account
            is_first_time_linking = not user.google_connected

        # Sub-accounts cannot link Google directly - only their admin can
        if user_type == "sub_account":
            return RedirectResponse(url="/?error=sub_account_cannot_link")

        # Only store tokens and set connected status if ALL permissions granted
        user.google_access_token = creds.token
        if creds.refresh_token:
            user.google_refresh_token = creds.refresh_token
        user.google_connected = True

        if not user.google_spreadsheet_id:
            try:
                from backend.google_utils import create_spreadsheet_in_folder

                ssid = create_spreadsheet_in_folder(creds)
                if ssid:
                    user.google_spreadsheet_id = ssid
            except:
                pass

        # If this is an enterprise admin, create sheets for all existing sub-accounts
        if user_type == "enterprise_admin":
            try:
                stmt = select(SubAccount).where(SubAccount.admin_id == user.id)
                sub_accounts = db.exec(stmt).all()
                for sub in sub_accounts:
                    if not sub.sheet_name:
                        create_sub_account_sheet(user, sub, db)
            except Exception as e:
                print(f"Warning: Could not create sheets for sub-accounts: {e}")

        # SINGLE-DEVICE ENFORCEMENT: Create new session, invalidating any previous ones
        session_id = str(uuid.uuid4())
        user.current_session_id = session_id
        db.add(user)
        if not safe_commit(db):
            raise HTTPException(status_code=500, detail="Failed to update session")

        # Get correct identifier based on user type
        identifier = getattr(user, "email", None) or getattr(user, "username")
        app_token = create_access_token(
            data={"sub": identifier, "sid": session_id, "type": user_type}
        )

        # Only show "Google account linked" notification on first-time linking
        if is_first_time_linking:
            return RedirectResponse(url=f"/?token={app_token}&google_linked=success")
        else:
            return RedirectResponse(url=f"/?token={app_token}")

    except Exception as e:
        return {"error": f"Google Auth Failed: {str(e)}"}


@app.get("/api/auth/google/verify")
def verify_google_status(token: str, db: Session = Depends(get_session)):
    """Explicitly checks if the Google token is valid and has permissions."""
    user, user_type = get_current_user_multi(token, db)

    if not is_google_connected(user, user_type, db):
        raise HTTPException(status_code=400, detail="Google Account not connected")

    try:
        # Get the actual user object that has Google credentials
        google_user = get_admin_for_user(user, user_type, db)
        verify_connection_health(google_user, db)
        return {"status": "valid", "detail": "Connection Healthy"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 5. CORE PROCESSING LOGIC
# ==========================================


async def async_process_image_logic(image_bytes: bytes, raw_text: str = ""):
    print(f"\n{'=' * 60}")
    print(f"[AI PROCESSING ASYNC] Starting AI processing")
    print(f"[AI PROCESSING ASYNC] Image size: {len(image_bytes)} bytes")
    print(f"[AI PROCESSING ASYNC] OCR text length: {len(raw_text)} chars")
    print(f"[AI PROCESSING ASYNC] OCR text preview: {raw_text[:200]}...")
    print(f"[AI PROCESSING ASYNC] Using model: {settings.LLM_MODEL}")

    # Check if the model supports vision (multimodal)
    # Vision models: gemini/, gpt-4-vision, claude-3, etc.
    # Text-only models: groq/, gpt-3.5, etc.
    is_vision_model = any(
        prefix in settings.LLM_MODEL.lower()
        for prefix in ["gemini/", "gpt-4-vision", "claude-3"]
    )
    print(f"[AI PROCESSING ASYNC] Is vision model: {is_vision_model}")

    if is_vision_model:
        # Use multimodal approach (image + text)
        print(f"[AI PROCESSING ASYNC] Using VISION model approach (image + text)")
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        system_prompt = f"""
        You are an expert data extraction AI.
        Extract contact details into this valid JSON object matching this schema exactly:
        {json.dumps(VCF_SCHEMA)}

        CRITICAL: Analyze the business nature (e.g. Plumbing, IT Services, Legal, Forex Trading) based on the text and populate the 'cat' field. DO NOT MAKE UP ANY FIELDS AND ONLY USE THE INFORMATION PROVIDED.
        OCR Text Context: {raw_text}
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": system_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ]
    else:
        # Use text-only approach (OCR text only)
        print(f"[AI PROCESSING ASYNC] Using TEXT-ONLY model approach (OCR text only)")
        system_prompt = f"""
        You are an expert data extraction AI.
        Extract contact details from the following business card text into this valid JSON object matching this schema exactly:
        {json.dumps(VCF_SCHEMA)}

        CRITICAL: Analyze the business nature (e.g. Plumbing, IT Services, Legal, Forex Trading) based on the text and populate the 'cat' field. DO NOT MAKE UP ANY FIELDS AND ONLY USE THE INFORMATION PROVIDED.

        Business Card Text:
        {raw_text}
        """
        messages = [{"role": "user", "content": system_prompt}]

    try:
        print(f"[AI PROCESSING ASYNC] Sending request to AI model...")

        # Determine the provider and model name
        if settings.LLM_MODEL.startswith("gemini/"):
            # Let LiteLLM handle Gemini routing automatically
            model_name = settings.LLM_MODEL
            api_params = {
                "model": model_name,
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
        else:
            # Force Groq provider for all other models
            # Preserve the full model name and just ensure groq/ prefix
            if settings.LLM_MODEL.startswith("groq/"):
                model_name = settings.LLM_MODEL
            else:
                # Prepend groq/ to the model name (preserves any existing prefixes like openai/gpt-oss-20b)
                model_name = f"groq/{settings.LLM_MODEL}"

            print(f"[AI PROCESSING ASYNC] Using Groq provider with model: {model_name}")

            api_params = {
                "model": model_name,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "custom_llm_provider": "groq",
            }

        response = await acompletion(**api_params)
        print(f"[AI PROCESSING ASYNC] ✅ Received response from AI")

        content = response.choices[0].message.content
        print(f"[AI PROCESSING ASYNC] Response content length: {len(content)} chars")
        print(f"[AI PROCESSING ASYNC] Response preview: {content[:500]}...")

        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "")
            print(f"[AI PROCESSING ASYNC] Removed markdown JSON formatting")

        data = json.loads(content)
        print(f"[AI PROCESSING ASYNC] ✅ Successfully parsed JSON")
        print(f"[AI PROCESSING ASYNC] Extracted data keys: {list(data.keys())}")
        print(f"[AI PROCESSING ASYNC] Full extracted data: {data}")

        if isinstance(data, list):
            result = data[0] if len(data) > 0 else {}
            print(f"[AI PROCESSING ASYNC] Data was list, returning first element")
        else:
            result = data

        print(f"[AI PROCESSING ASYNC] ✅ Final result: {result}")
        print(f"{'=' * 60}\n")
        return result
    except Exception as e:
        print(f"[AI PROCESSING ASYNC] ❌ Error: {type(e).__name__}: {e}")
        import traceback

        print(f"[AI PROCESSING ASYNC] Traceback: {traceback.format_exc()}")
        print(f"{'=' * 60}\n")
        return {}


def sync_process_image_logic(image_bytes: bytes) -> dict:
    print(f"\n{'=' * 60}")
    print(f"[AI PROCESSING SYNC] Starting AI processing")
    print(f"[AI PROCESSING SYNC] Image size: {len(image_bytes)} bytes")
    print(f"[AI PROCESSING SYNC] Using model: {settings.LLM_MODEL}")

    # Extract OCR text using abstraction layer
    ocr_service = get_ocr_service()
    ocr_result = ocr_service.extract_sync(image_bytes)
    raw_text = ocr_result.full_text
    print(f"[AI PROCESSING SYNC] OCR text length: {len(raw_text)} chars")
    print(f"[AI PROCESSING SYNC] OCR text preview: {raw_text[:200]}...")

    # Check if the model supports vision (multimodal)
    is_vision_model = any(
        prefix in settings.LLM_MODEL.lower()
        for prefix in ["gemini/", "gpt-4-vision", "claude-3"]
    )
    print(f"[AI PROCESSING SYNC] Is vision model: {is_vision_model}")

    if is_vision_model:
        # Use multimodal approach (image + text)
        print(f"[AI PROCESSING SYNC] Using VISION model approach (image + text)")
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        system_prompt = f"Extract JSON Schema: {json.dumps(VCF_SCHEMA)}\nAnalyze Business Category (e.g. Plumbing, Legal) into 'cat' field.\nOCR: {raw_text}"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": system_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            }
        ]
    else:
        # Use text-only approach (OCR text only)
        print(f"[AI PROCESSING SYNC] Using TEXT-ONLY model approach (OCR text only)")
        system_prompt = f"""Extract contact details from the following business card text into this valid JSON object matching this schema exactly:
{json.dumps(VCF_SCHEMA)}

CRITICAL: Analyze the business nature (e.g. Plumbing, IT Services, Legal, Forex Trading) based on the text and populate the 'cat' field. DO NOT MAKE UP ANY FIELDS AND ONLY USE THE INFORMATION PROVIDED.

Business Card Text:
{raw_text}
"""
        messages = [{"role": "user", "content": system_prompt}]

    try:
        print(f"[AI PROCESSING SYNC] Sending request to AI model...")

        # Determine the provider and model name - same logic as async version
        if settings.LLM_MODEL.startswith("gemini/"):
            # Let LiteLLM handle Gemini routing automatically
            model_name = settings.LLM_MODEL
            api_params = {
                "model": model_name,
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
        else:
            # Force Groq provider for all other models
            # Preserve the full model name and just ensure groq/ prefix
            if settings.LLM_MODEL.startswith("groq/"):
                model_name = settings.LLM_MODEL
            else:
                # Prepend groq/ to the model name (preserves any existing prefixes like openai/gpt-oss-20b)
                model_name = f"groq/{settings.LLM_MODEL}"

            print(f"[AI PROCESSING SYNC] Using Groq provider with model: {model_name}")

            api_params = {
                "model": model_name,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "custom_llm_provider": "groq",
            }

        response = completion(**api_params)
        print(f"[AI PROCESSING SYNC] ✅ Received response from AI")

        content = response.choices[0].message.content
        print(f"[AI PROCESSING SYNC] Response content length: {len(content)} chars")
        print(f"[AI PROCESSING SYNC] Response preview: {content[:500]}...")

        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "")
            print(f"[AI PROCESSING SYNC] Removed markdown JSON formatting")

        data = json.loads(content)
        print(f"[AI PROCESSING SYNC] ✅ Successfully parsed JSON")
        print(f"[AI PROCESSING SYNC] Extracted data keys: {list(data.keys())}")
        print(f"[AI PROCESSING SYNC] Full extracted data: {data}")

        if isinstance(data, list):
            result = data[0] if len(data) > 0 else {}
            print(f"[AI PROCESSING SYNC] Data was list, returning first element")
        else:
            result = data

        print(f"[AI PROCESSING SYNC] ✅ Final result: {result}")
        print(f"{'=' * 60}\n")
        return result
    except Exception as e:
        print(f"[AI PROCESSING SYNC] ❌ Error: {type(e).__name__}: {e}")
        import traceback

        print(f"[AI PROCESSING SYNC] Traceback: {traceback.format_exc()}")
        print(f"{'=' * 60}\n")
        return {}


# --- EMAIL LOGIC ---
def normalize_emails(email_input) -> list:
    import re

    if not email_input:
        return []
    if isinstance(email_input, str):
        email_input = [email_input]
    valid_emails = []
    email_regex = r"[^@\s]+@[^@\s]+\.[^@\s]+"
    for item in email_input:
        if not item:
            continue
        parts = re.split(r"[;,\s\n]+", str(item))
        for part in parts:
            part = part.strip().strip(".'\"")
            if part and re.match(email_regex, part):
                valid_emails.append(part)
    return list(set(valid_emails))


def replace_template_variables(text: str, contact_data: dict) -> str:
    """
    Programmatically replace {{ variable }} placeholders with actual contact data.
    Supports conditional blocks that are removed if the variable is empty.

    Supported variables:
    - {{ name }} or {{ full_name }} - Contact's full name
    - {{ first_name }} - First name only
    - {{ last_name }} - Last name only
    - {{ company }} or {{ organization }} - Company/organization name
    - {{ email }} - Primary email address
    - {{ phone }} - Primary phone number
    - {{ address }} - Primary address
    - {{ website }} or {{ url }} - Primary website
    - {{ category }} - Business category
    - {{ notes }} - AI-generated notes
    - {{ title }} or {{ job_title }} - Job title

    Conditional syntax:
    {{% if variable %}}Content here with {{ variable }}{{% endif %}}
    If variable is empty, the entire block is removed.
    """
    import re

    # Extract contact data with defaults
    full_name = contact_data.get("fn", [""])[0] if contact_data.get("fn") else ""
    name_parts = full_name.split(" ", 1) if full_name else ["", ""]
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    company = contact_data.get("org", "") or ""
    email = contact_data.get("email", [""])[0] if contact_data.get("email") else ""
    phone = contact_data.get("tel", [""])[0] if contact_data.get("tel") else ""
    address = contact_data.get("adr", [""])[0] if contact_data.get("adr") else ""
    website = contact_data.get("url", [""])[0] if contact_data.get("url") else ""
    category = contact_data.get("cat", [""])[0] if contact_data.get("cat") else ""
    notes = contact_data.get("notes", "") or ""
    job_title = contact_data.get("title", "") or ""

    # Define variable mappings
    replacements = {
        "name": full_name,
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "company": company,
        "organization": company,
        "org": company,
        "email": email,
        "phone": phone,
        "tel": phone,
        "address": address,
        "adr": address,
        "website": website,
        "url": website,
        "category": category,
        "notes": notes,
        "title": job_title,
        "job_title": job_title,
    }

    result = text

    # Process conditional blocks first: {{% if variable %}}content{{% endif %}}
    conditional_pattern = r"\{\{%\s*if\s+(\w+)\s*%\}\}(.*?)\{\{%\s*endif\s*%\}\}"

    def replace_conditional(match):
        var_name = match.group(1).lower()
        content = match.group(2)
        # Check if variable has value
        var_value = replacements.get(var_name, "")
        if var_value and var_value.strip():
            return content  # Keep content if variable has value
        else:
            return ""  # Remove entire block if variable is empty

    result = re.sub(
        conditional_pattern,
        replace_conditional,
        result,
        flags=re.IGNORECASE | re.DOTALL,
    )

    # Replace all {{ variable }} patterns
    for var_name, var_value in replacements.items():
        # Match {{ var_name }} with optional whitespace
        pattern = r"\{\{\s*" + var_name + r"\s*\}\}"
        result = re.sub(pattern, var_value or "", result, flags=re.IGNORECASE)

    return result


async def process_and_send_email(
    user_email: str, contact_data: dict, db_session: Session
):
    """
    Process and send email using programmatic variable replacement.
    Variables in the template are replaced with actual contact data.
    """
    statement = select(User).where(User.email == user_email)
    user = db_session.exec(statement).first()
    if not user or not user.email_feature_enabled:
        return
    emails = normalize_emails(contact_data.get("email", []))
    if not emails:
        return

    try:
        templates = fetch_templates(user, db_session)
        active_tpl = next((t for t in templates if t["active"] == "TRUE"), None)
        if not active_tpl:
            return

        # Programmatically replace variables in subject and body
        subject = replace_template_variables(active_tpl["subject"], contact_data)
        body = replace_template_variables(active_tpl["body"], contact_data)

        # Convert newlines to HTML line breaks for proper email formatting
        body_html = body.replace("\n", "<br>")

        # Parse and resolve attachments if present
        attachments = None
        if active_tpl.get("attachment"):
            try:
                attachment_refs = json.loads(active_tpl["attachment"])
                attachments = get_template_attachments(
                    user, db_session, attachment_refs
                )
            except:
                pass

        # Send emails
        for email_addr in emails:
            try:
                send_gmail(
                    user, db_session, email_addr, subject, body_html, attachments
                )
            except:
                pass
    except:
        pass


def sync_email_generation_and_send(user: User, db: Session, contact_data: dict):
    """
    Synchronous version of email sending with programmatic variable replacement.
    """
    emails = normalize_emails(contact_data.get("email", []))
    if not emails:
        return
    try:
        templates = fetch_templates(user, db)
        active_tpl = next((t for t in templates if t["active"] == "TRUE"), None)
        if not active_tpl:
            return

        # Programmatically replace variables
        subject = replace_template_variables(active_tpl["subject"], contact_data)
        body = replace_template_variables(active_tpl["body"], contact_data)

        # Convert newlines to HTML line breaks for proper email formatting
        body_html = body.replace("\n", "<br>")

        # Parse and resolve attachments if present
        attachments = None
        if active_tpl.get("attachment"):
            try:
                attachment_refs = json.loads(active_tpl["attachment"])
                attachments = get_template_attachments(user, db, attachment_refs)
            except:
                pass

        # Send emails
        for email_addr in emails:
            try:
                send_gmail(user, db, email_addr, subject, body_html, attachments)
            except:
                pass
    except:
        pass


async def process_and_send_email_admin(
    admin_username: str, contact_data: dict, db_session: Session
):
    """
    Send email for enterprise admin using their active template.
    Uses programmatic variable replacement.
    """
    statement = select(EnterpriseAdmin).where(
        EnterpriseAdmin.username == admin_username
    )
    admin = db_session.exec(statement).first()
    if not admin or not admin.email_feature_enabled:
        return

    emails = normalize_emails(contact_data.get("email", []))
    if not emails:
        return

    try:
        templates = fetch_templates(admin, db_session)
        active_tpl = next((t for t in templates if t["active"] == "TRUE"), None)
        if not active_tpl:
            return

        # Programmatically replace variables
        subject = replace_template_variables(active_tpl["subject"], contact_data)
        body = replace_template_variables(active_tpl["body"], contact_data)

        # Convert newlines to HTML line breaks for proper email formatting
        body_html = body.replace("\n", "<br>")

        # Parse and resolve attachments if present
        attachment = None
        if active_tpl.get("attachment"):
            try:
                attachment_refs = json.loads(active_tpl["attachment"])
                attachment = get_template_attachments(
                    admin, db_session, attachment_refs
                )
            except:
                pass

        # Send emails
        for email_addr in emails:
            try:
                send_gmail(
                    admin, db_session, email_addr, subject, body_html, attachment
                )
            except:
                pass
    except:
        pass


async def process_and_send_email_enterprise(
    admin: EnterpriseAdmin, contact_data: dict, template: dict, db_session: Session
):
    """
    Send email for enterprise sub-account using admin's Gmail and assigned template.
    Uses programmatic variable replacement.
    """
    emails = normalize_emails(contact_data.get("email", []))
    if not emails:
        return

    try:
        # Programmatically replace variables
        subject = replace_template_variables(template["subject"], contact_data)
        body = replace_template_variables(template["body"], contact_data)

        # Convert newlines to HTML line breaks for proper email formatting
        body_html = body.replace("\n", "<br>")

        # Parse and resolve attachments if present
        attachments = None
        if template.get("attachment"):
            try:
                attachment_refs = json.loads(template["attachment"])
                attachments = get_template_attachments(
                    admin, db_session, attachment_refs
                )
            except:
                pass

        # Send emails
        for email_addr in emails:
            try:
                send_gmail(
                    admin, db_session, email_addr, subject, body_html, attachments
                )
            except:
                pass
    except:
        pass


def background_bulk_worker(user_identifier: str, db_session: Session):
    """Background worker for single users and enterprise admins."""
    # Try to find user by email (single user)
    statement = select(User).where(User.email == user_identifier)
    user = db_session.exec(statement).first()

    # If not found, try enterprise admin by email
    if not user:
        statement = select(EnterpriseAdmin).where(
            EnterpriseAdmin.email == user_identifier
        )
        user = db_session.exec(statement).first()

    if not user:
        return
    process_bulk_queue_sync(
        user,
        db_session,
        process_func=sync_process_image_logic,
        email_func=sync_email_generation_and_send,
    )


def background_bulk_worker_sub_account(
    admin_id: int, sub_account_id: int, db_session: Session
):
    """Background worker for sub-accounts."""
    admin_stmt = select(EnterpriseAdmin).where(EnterpriseAdmin.id == admin_id)
    admin = db_session.exec(admin_stmt).first()

    sub_stmt = select(SubAccount).where(SubAccount.id == sub_account_id)
    sub_account = db_session.exec(sub_stmt).first()

    if not admin or not sub_account:
        return

    # Import the sub-account bulk processor
    from backend.google_utils import process_bulk_queue_sync_sub_account

    # Get the assigned template for this sub-account
    template = None
    if sub_account.assigned_template_id:
        templates = fetch_templates(admin, db_session)
        template = next(
            (t for t in templates if t["id"] == sub_account.assigned_template_id), None
        )

    process_bulk_queue_sync_sub_account(
        admin,
        sub_account,
        db_session,
        process_func=sync_process_image_logic,
        template=template,
    )


# ==========================================
# 7. SCANNING & BULK ENDPOINTS
# ==========================================


@app.post("/api/scan")
async def scan_card(
    file: UploadFile = File(...),
    token: str = None,
    bulk_stage: bool = False,
    db: Session = Depends(get_session),
):
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    user, user_type = get_current_user_multi(token, db)
    file_bytes = await file.read()

    # LICENSE AND SCAN LIMIT CHECK FOR SINGLE USERS
    if user_type == "single":
        # Check if user has a valid license
        user_license = None
        if user.license_id:
            license_stmt = select(License).where(License.id == user.license_id)
            user_license = db.exec(license_stmt).first()

        has_valid_license = is_license_valid(user_license)

        # If no valid license, enforce scan limit from config
        if not has_valid_license:
            if user.scan_count >= settings.FREE_TIER_SCAN_LIMIT:
                raise HTTPException(
                    status_code=403,
                    detail=f"Scan limit reached. You have used all {settings.FREE_TIER_SCAN_LIMIT} free scans for unlicensed accounts. Please contact a distributor to upgrade to a licensed account for unlimited scanning.",
                )

            # Increment scan count after successful scan (will be committed at the end)
            user.scan_count += 1
            db.add(user)
            db.commit()
            db.refresh(user)

    # MODE A: BULK STAGING
    if bulk_stage:
        if not is_google_connected(user, user_type, db):
            raise HTTPException(
                status_code=403, detail="Please link Google Account for Bulk Mode."
            )

        try:
            # Get the admin (for sub-accounts, this is their admin; for others, it's themselves)
            admin = get_admin_for_user(user, user_type, db)

            filename = (
                f"bulk_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:4]}.jpg"
            )

            # For bulk staging, we need to handle sub-accounts specially
            if user_type == "sub_account":
                # Sub-accounts stage to admin's Drive but use their own staging sheet
                file_id = stage_bulk_image_sub_account(
                    admin, user, db, file_bytes, filename
                )
            else:
                file_id = stage_bulk_image(admin, db, file_bytes, filename)

            count = check_staging_count_for_user(admin, user, user_type, db)
            return {"status": "staged", "count": count, "file_id": file_id}
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload Failed: {str(e)}")

    # MODE B: SINGLE SCAN
    print(f"\n{'#' * 80}")
    print(f"[SCAN ENDPOINT] === SINGLE SCAN MODE ===")
    print(f"[SCAN ENDPOINT] Filename: {file.filename}")
    print(f"[SCAN ENDPOINT] Content-Type: {file.content_type}")
    print(f"[SCAN ENDPOINT] File size: {len(file_bytes)} bytes")
    print(
        f"[SCAN ENDPOINT] User: {user.email if hasattr(user, 'email') else user.username}"
    )
    print(f"[SCAN ENDPOINT] User type: {user_type}")
    print(f"{'#' * 80}\n")

    # Extract OCR text using abstraction layer
    print(f"[SCAN ENDPOINT] Step 1: Calling OCR service...")
    ocr_service = get_ocr_service()
    ocr_result = await ocr_service.extract_async(file_bytes, file.filename)
    raw_text = ocr_result.full_text
    print(f"[SCAN ENDPOINT] Step 1 Complete: OCR extracted {len(raw_text)} characters")
    print(f"[SCAN ENDPOINT] OCR text: {raw_text[:300]}...")

    print(f"[SCAN ENDPOINT] Step 2: Calling AI processing...")
    structured_data = await async_process_image_logic(file_bytes, raw_text)
    print(
        f"[SCAN ENDPOINT] Step 2 Complete: AI returned data with keys: {list(structured_data.keys())}"
    )

    result = {"raw_text": raw_text, "structured": structured_data}
    print(f"[SCAN ENDPOINT] ✅ Final result to return: {result}")
    print(f"\n{'#' * 80}\n")
    return result


@app.post("/api/bulk/submit")
def submit_bulk(
    token: str, background_tasks: BackgroundTasks, db: Session = Depends(get_session)
):
    user, user_type = get_current_user_multi(token, db)
    if not is_google_connected(user, user_type, db):
        raise HTTPException(status_code=400, detail="Google not connected")

    admin = get_admin_for_user(user, user_type, db)

    try:
        if user_type == "sub_account":
            count = submit_bulk_session_sub_account(admin, user, db)
            if count > 0:
                background_tasks.add_task(
                    background_bulk_worker_sub_account, admin.id, user.id, db
                )
        else:
            count = submit_bulk_session(admin, db)
            if count > 0:
                identifier = getattr(admin, "email", None) or getattr(admin, "username")
                background_tasks.add_task(background_bulk_worker, identifier, db)

        return {"status": "submitted", "count": count}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bulk/cancel")
def cancel_bulk(token: str, db: Session = Depends(get_session)):
    user, user_type = get_current_user_multi(token, db)
    admin = get_admin_for_user(user, user_type, db)

    try:
        if user_type == "sub_account":
            clear_staging_data_sub_account(admin, user, db)
        else:
            clear_staging_data(admin, db)
        return {"status": "cleared"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bulk/check")
def check_bulk_status(token: str, db: Session = Depends(get_session)):
    user, user_type = get_current_user_multi(token, db)
    if not is_google_connected(user, user_type, db):
        return {"count": 0}

    admin = get_admin_for_user(user, user_type, db)

    try:
        count = check_staging_count_for_user(admin, user, user_type, db)
        return {"count": count}
    except HTTPException as e:
        raise e
    except:
        return {"count": 0}


# ==========================================
# 8. CONTACT SAVING & EXPORT
# ==========================================


@app.post("/api/contacts/save")
def save_contact_to_google(
    contact: ContactSave,
    token: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
):
    user, user_type = get_current_user_multi(token, db)

    # Build contact row data
    cat_str = ", ".join(contact.cat) if contact.cat else ""
    row_data = [
        ", ".join(contact.fn),
        contact.org,
        ", ".join(contact.tel),
        contact.title,
        ", ".join(contact.email),
        ", ".join(contact.url),
        ", ".join(contact.adr),
        "General",
        cat_str,
        contact.notes,
    ]

    try:
        # Handle different user types
        if user_type == "sub_account":
            # Sub-account: Save to their dedicated sheet in admin's spreadsheet
            admin_stmt = select(EnterpriseAdmin).where(
                EnterpriseAdmin.id == user.admin_id
            )
            admin = db.exec(admin_stmt).first()

            if not admin or not admin.google_connected:
                return {
                    "status": "skipped",
                    "detail": "Admin's Google account not connected.",
                }

            # Append to sub-account's sheet
            append_to_sub_account_sheet(admin, user, db, row_data)

            # Check if auto-email is enabled for this sub-account
            if user.assigned_template_id and contact.email:
                # Fetch the assigned template from admin's templates
                templates = fetch_templates(admin, db)
                assigned_template = next(
                    (t for t in templates if t["id"] == user.assigned_template_id), None
                )

                if assigned_template:
                    background_tasks.add_task(
                        process_and_send_email_enterprise,
                        admin,
                        contact.dict(),
                        assigned_template,
                        db,
                    )
                    return {
                        "status": "success",
                        "detail": "Saved to Google Sheet & Email Queued.",
                    }

            return {"status": "success", "detail": "Saved to Google Sheet."}

        elif user_type == "enterprise_admin":
            # Enterprise Admin: Save to their own main sheet (first sheet)
            if not user.google_connected:
                return {"status": "skipped", "detail": "Google not linked."}

            append_to_sheet(user, db, row_data)

            # For admin's own scanning, use the currently active template
            if user.email_feature_enabled and contact.email:
                background_tasks.add_task(
                    process_and_send_email_admin, user.username, contact.dict(), db
                )
                return {
                    "status": "success",
                    "detail": "Saved to Google Sheet & Email Queued.",
                }

            return {"status": "success", "detail": "Saved to Google Sheet."}

        else:  # Single user
            if not user.google_connected:
                return {
                    "status": "skipped",
                    "detail": "Saved locally only (Google not linked).",
                }

            append_to_sheet(user, db, row_data)

            if user.email_feature_enabled and contact.email:
                background_tasks.add_task(
                    process_and_send_email, user.email, contact.dict(), db
                )
                return {
                    "status": "success",
                    "detail": "Saved to Google Sheet & Email Queued.",
                }

            return {"status": "success", "detail": "Saved to Google Sheet."}

    except HTTPException as e:
        raise e
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/api/contacts/export")
def export_contacts(token: str, db: Session = Depends(get_session)):
    user, user_type = get_current_user_multi(token, db)

    if not is_google_connected(user, user_type, db):
        raise HTTPException(status_code=400, detail="Google not connected")

    creds = get_google_creds_for_user(user, user_type, db)
    if not creds:
        raise HTTPException(status_code=403, detail="Google Auth Revoked")

    spreadsheet_id = get_spreadsheet_id_for_user(user, user_type, db)
    if not spreadsheet_id:
        raise HTTPException(status_code=400, detail="No spreadsheet found")

    try:
        drive_service = build("drive", "v3", credentials=creds)
        file_data = (
            drive_service.files()
            .export_media(
                fileId=spreadsheet_id,
                mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            .execute()
        )
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=Card2Contacts_Contacts.xlsx"
            },
        )
    except HttpError as e:
        handle_google_api_error(e, "Exporting Contacts")


# ==========================================
# 9. EMAIL SETTINGS ENDPOINTS
# ==========================================


@app.get("/api/email/settings")
def get_email_settings(token: str, db: Session = Depends(get_session)):
    user, user_type = get_current_user_multi(token, db)

    # Sub-accounts don't have email settings - only admins do
    if user_type == "sub_account":
        raise HTTPException(
            status_code=403, detail="Email settings not available for sub-accounts"
        )

    if not is_google_connected(user, user_type, db):
        raise HTTPException(status_code=400, detail="Google not connected")

    try:
        google_user = get_admin_for_user(user, user_type, db)
        templates = fetch_templates(google_user, db)
        return {
            "enabled": google_user.email_feature_enabled,
            "templates": templates,
            "count": len(templates),
        }
    except HTTPException as e:
        raise e


@app.post("/api/email/toggle")
def toggle_email_feature(enabled: bool, token: str, db: Session = Depends(get_session)):
    user, user_type = get_current_user_multi(token, db)

    # Sub-accounts don't have email settings - only admins do
    if user_type == "sub_account":
        raise HTTPException(
            status_code=403, detail="Email settings not available for sub-accounts"
        )

    if enabled:
        try:
            google_user = get_admin_for_user(user, user_type, db)
            templates = fetch_templates(google_user, db)
            if not any(t["active"] == "TRUE" for t in templates):
                raise HTTPException(
                    status_code=400,
                    detail="Please set at least one active template before enabling.",
                )
        except HTTPException as e:
            raise e

    user.email_feature_enabled = enabled
    db.add(user)
    db.commit()
    return {"status": "success", "enabled": enabled}


@app.post("/api/email/templates")
def create_template_endpoint(
    tpl: TemplateCreate, token: str, db: Session = Depends(get_session)
):
    user, user_type = get_current_user_multi(token, db)
    if user_type == "sub_account":
        raise HTTPException(
            status_code=403, detail="Email settings not available for sub-accounts"
        )
    google_user = get_admin_for_user(user, user_type, db)
    return add_template(google_user, db, tpl.subject, tpl.body, tpl.attachments)


@app.put("/api/email/templates/{row_id}")
def update_template_endpoint(
    row_id: int, tpl: TemplateCreate, token: str, db: Session = Depends(get_session)
):
    user, user_type = get_current_user_multi(token, db)
    if user_type == "sub_account":
        raise HTTPException(
            status_code=403, detail="Email settings not available for sub-accounts"
        )
    google_user = get_admin_for_user(user, user_type, db)
    return update_template_content(
        google_user, db, row_id, tpl.subject, tpl.body, tpl.attachments
    )


@app.post("/api/email/templates/{row_id}/activate")
def activate_template_endpoint(
    row_id: int, active: bool, token: str, db: Session = Depends(get_session)
):
    user, user_type = get_current_user_multi(token, db)
    if user_type == "sub_account":
        raise HTTPException(
            status_code=403, detail="Email settings not available for sub-accounts"
        )
    google_user = get_admin_for_user(user, user_type, db)

    # Update template status
    result = set_active_template(google_user, db, row_id, active)

    # Check if any templates are active after this change
    templates = fetch_templates(google_user, db)
    has_active_template = any(t["active"] == "TRUE" for t in templates)

    # Auto-disable email feature if no active templates
    if not has_active_template and user.email_feature_enabled:
        user.email_feature_enabled = False
        db.add(user)
        db.commit()
        result["email_auto_disabled"] = True

    return result


# ==========================================
# 10. ENTERPRISE ADMIN PANEL ENDPOINTS
# ==========================================


@app.get("/api/admin/license")
def get_license_info(token: str, db: Session = Depends(get_session)):
    """Get license info and usage stats for enterprise admin."""
    admin = get_current_admin(token, db)

    # Get license
    license_stmt = select(License).where(License.id == admin.license_id)
    license_record = db.exec(license_stmt).first()

    if not license_record:
        raise HTTPException(status_code=404, detail="License not found")

    # Count current sub-accounts
    sub_count_stmt = select(SubAccount).where(SubAccount.admin_id == admin.id)
    sub_accounts = db.exec(sub_count_stmt).all()

    limits = json.loads(license_record.limits)

    # Check if license is expired
    license_valid = is_license_valid(license_record)
    license_expires_at = license_record.created_at + timedelta(days=365)

    return {
        "license_key": license_record.license_key[:8]
        + "..."
        + license_record.license_key[-4:],
        "is_active": license_record.is_active,
        "is_valid": license_valid,
        "created_at": license_record.created_at.isoformat(),
        "expires_at": license_expires_at.isoformat(),
        "limits": limits,
        "current_sub_accounts": len(sub_accounts),
        "max_sub_accounts": limits.get("max_sub_accounts", 5),
    }


@app.post("/api/admin/expand-seats")
def expand_seats(
    data: SeatExpansionRequest, token: str, db: Session = Depends(get_session)
):
    """Expand the number of available seats for enterprise admin's license."""
    admin = get_current_admin(token, db)

    # Validate additional seats
    if data.additional_seats <= 0:
        raise HTTPException(
            status_code=400, detail="Additional seats must be greater than 0"
        )

    # Get license
    license_stmt = select(License).where(License.id == admin.license_id)
    license_record = db.exec(license_stmt).first()

    if not license_record:
        raise HTTPException(status_code=404, detail="License not found")

    # Check if license is active
    if not license_record.is_active:
        raise HTTPException(status_code=403, detail="License is not active")

    # Parse current limits
    limits = json.loads(license_record.limits)
    current_max = limits.get("max_sub_accounts", 5)

    # Update limits with additional seats
    new_max = current_max + data.additional_seats
    limits["max_sub_accounts"] = new_max

    # Update license in database
    license_record.limits = json.dumps(limits)
    db.add(license_record)
    db.commit()
    db.refresh(license_record)

    # Count current sub-accounts
    sub_count_stmt = select(SubAccount).where(SubAccount.admin_id == admin.id)
    current_count = len(db.exec(sub_count_stmt).all())

    return {
        "status": "success",
        "message": f"Successfully added {data.additional_seats} seats to your license",
        "previous_max": current_max,
        "new_max": new_max,
        "current_sub_accounts": current_count,
        "available_seats": new_max - current_count,
    }


@app.get("/api/admin/sub-accounts")
def list_sub_accounts(token: str, db: Session = Depends(get_session)):
    """List all sub-accounts for this enterprise admin."""
    admin = get_current_admin(token, db)

    stmt = select(SubAccount).where(SubAccount.admin_id == admin.id)
    sub_accounts = db.exec(stmt).all()

    return {
        "sub_accounts": [
            {
                "id": sub.id,
                "email": sub.email,  # For sub-accounts, this is the username string
                "is_active": sub.is_active,
                "created_at": sub.created_at.isoformat() if sub.created_at else None,
                "is_logged_in": sub.current_session_id is not None,
                "assigned_template_id": sub.assigned_template_id,
            }
            for sub in sub_accounts
        ],
        "count": len(sub_accounts),
    }


@app.post("/api/admin/sub-accounts")
def create_sub_account(
    data: SubAccountCreate, token: str, db: Session = Depends(get_session)
):
    """Create a new sub-account under this enterprise admin."""
    admin = get_current_admin(token, db)

    # Check license limits and expiration
    license_stmt = select(License).where(License.id == admin.license_id)
    license_record = db.exec(license_stmt).first()

    if not is_license_valid(license_record):
        if license_record and not license_record.is_active:
            raise HTTPException(status_code=403, detail="License is not active")
        elif license_record:
            raise HTTPException(
                status_code=403,
                detail="License has expired. Please renew your license to create sub-accounts.",
            )
        else:
            raise HTTPException(status_code=403, detail="No valid license found")

    limits = json.loads(license_record.limits)
    max_subs = limits.get("max_sub_accounts", 5)

    # Count current sub-accounts
    current_count_stmt = select(SubAccount).where(SubAccount.admin_id == admin.id)
    current_count = len(db.exec(current_count_stmt).all())

    if current_count >= max_subs:
        raise HTTPException(
            status_code=403, detail=f"License limit reached ({max_subs} sub-accounts)"
        )

    # Check email uniqueness across all user types
    email_check = select(SubAccount).where(SubAccount.email == data.email)
    if db.exec(email_check).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Also check against enterprise admins and regular users
    admin_check = select(EnterpriseAdmin).where(EnterpriseAdmin.email == data.email)
    if db.exec(admin_check).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user_check = select(User).where(User.email == data.email)
    if db.exec(user_check).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create sub-account
    sub = SubAccount(
        email=data.email,  # For sub-accounts, this is the username string
        password_hash=get_password_hash(data.password),
        admin_id=admin.id,
        is_active=True,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    # Create dedicated sheet for this sub-account in admin's spreadsheet
    # Only if admin has Google connected
    if admin.google_connected and admin.google_spreadsheet_id:
        try:
            create_sub_account_sheet(admin, sub, db)
        except Exception as e:
            print(f"Warning: Could not create sheet for sub-account: {e}")
            # Don't fail the sub-account creation if sheet creation fails

    return {
        "status": "success",
        "sub_account": {
            "id": sub.id,
            "email": sub.email,  # For sub-accounts, this is the username string
            "is_active": sub.is_active,
            "sheet_name": sub.sheet_name,
        },
    }


@app.put("/api/admin/sub-accounts/{sub_id}")
def update_sub_account(
    sub_id: int, data: SubAccountUpdate, token: str, db: Session = Depends(get_session)
):
    """Update a sub-account's email or password."""
    admin = get_current_admin(token, db)

    # Find sub-account (must belong to this admin)
    stmt = select(SubAccount).where(
        SubAccount.id == sub_id, SubAccount.admin_id == admin.id
    )
    sub = db.exec(stmt).first()

    if not sub:
        raise HTTPException(status_code=404, detail="Sub-account not found")

    # Update email if provided
    if data.email and data.email != sub.email:
        # Check uniqueness across all user types
        email_check = select(SubAccount).where(SubAccount.email == data.email)
        if db.exec(email_check).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        admin_check = select(EnterpriseAdmin).where(EnterpriseAdmin.email == data.email)
        if db.exec(admin_check).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        user_check = select(User).where(User.email == data.email)
        if db.exec(user_check).first():
            raise HTTPException(status_code=400, detail="Email already registered")

        sub.email = data.email
        # Invalidate session when email changes
        sub.current_session_id = None

    # Update password if provided
    if data.password:
        sub.password_hash = get_password_hash(data.password)
        # Invalidate session when password changes
        sub.current_session_id = None

    db.add(sub)
    db.commit()

    return {"status": "success", "message": "Sub-account updated"}


@app.post("/api/admin/sub-accounts/{sub_id}/toggle")
def toggle_sub_account(
    sub_id: int, active: bool, token: str, db: Session = Depends(get_session)
):
    """Activate or deactivate a sub-account."""
    admin = get_current_admin(token, db)

    stmt = select(SubAccount).where(
        SubAccount.id == sub_id, SubAccount.admin_id == admin.id
    )
    sub = db.exec(stmt).first()

    if not sub:
        raise HTTPException(status_code=404, detail="Sub-account not found")

    sub.is_active = active
    if not active:
        # Force logout when deactivating
        sub.current_session_id = None

    db.add(sub)
    db.commit()

    return {"status": "success", "is_active": sub.is_active}


@app.delete("/api/admin/sub-accounts/{sub_id}")
def delete_sub_account(sub_id: int, token: str, db: Session = Depends(get_session)):
    """Delete a sub-account permanently."""
    admin = get_current_admin(token, db)

    stmt = select(SubAccount).where(
        SubAccount.id == sub_id, SubAccount.admin_id == admin.id
    )
    sub = db.exec(stmt).first()

    if not sub:
        raise HTTPException(status_code=404, detail="Sub-account not found")

    db.delete(sub)
    db.commit()

    return {"status": "success", "message": "Sub-account deleted"}


# ==========================================
# 11. ENTERPRISE EXPORTS & TEMPLATE ASSIGNMENT
# ==========================================


@app.get("/api/admin/export/my-contacts")
def export_admin_own_contacts(token: str, db: Session = Depends(get_session)):
    """Export admin's own contacts (first sheet)."""
    admin = get_current_admin(token, db)

    if not admin.google_connected:
        raise HTTPException(status_code=400, detail="Google not connected")

    try:
        file_data, filename = export_sheet_as_excel(admin, db, sheet_name="Sheet1")
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except HttpError as e:
        handle_google_api_error(e, "Exporting Admin Contacts")


@app.get("/api/admin/export/sub-account/{sub_id}")
def export_sub_account_contacts(
    sub_id: int, token: str, db: Session = Depends(get_session)
):
    """Export a specific sub-account's contacts."""
    admin = get_current_admin(token, db)

    if not admin.google_connected:
        raise HTTPException(status_code=400, detail="Google not connected")

    # Find sub-account
    stmt = select(SubAccount).where(
        SubAccount.id == sub_id, SubAccount.admin_id == admin.id
    )
    sub = db.exec(stmt).first()

    if not sub:
        raise HTTPException(status_code=404, detail="Sub-account not found")

    if not sub.sheet_name:
        raise HTTPException(status_code=404, detail="Sub-account sheet not created yet")

    try:
        file_data, filename = export_sheet_as_excel(
            admin, db, sheet_name=sub.sheet_name
        )
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except HttpError as e:
        handle_google_api_error(e, "Exporting Sub-Account Contacts")


@app.get("/api/admin/export/all-combined")
def export_all_combined_contacts(token: str, db: Session = Depends(get_session)):
    """Export all contacts (admin + all sub-accounts) as one Excel file."""
    admin = get_current_admin(token, db)

    if not admin.google_connected:
        raise HTTPException(status_code=400, detail="Google not connected")

    try:
        # Get all sub-accounts
        stmt = select(SubAccount).where(SubAccount.admin_id == admin.id)
        sub_accounts = db.exec(stmt).all()

        file_data, filename = export_combined_contacts(admin, list(sub_accounts), db)
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except HttpError as e:
        handle_google_api_error(e, "Exporting Combined Contacts")


@app.post("/api/admin/sub-accounts/{sub_id}/assign-template")
def assign_template_to_sub_account(
    sub_id: int, template_id: str, token: str, db: Session = Depends(get_session)
):
    """Assign an email template to a sub-account for auto-mailing."""
    admin = get_current_admin(token, db)

    # Find sub-account
    stmt = select(SubAccount).where(
        SubAccount.id == sub_id, SubAccount.admin_id == admin.id
    )
    sub = db.exec(stmt).first()

    if not sub:
        raise HTTPException(status_code=404, detail="Sub-account not found")

    # Verify template exists in admin's templates
    if template_id != "none":  # "none" means disable auto-email
        templates = fetch_templates(admin, db)
        if not any(t["id"] == template_id for t in templates):
            raise HTTPException(status_code=404, detail="Template not found")

    # Assign template
    sub.assigned_template_id = None if template_id == "none" else template_id
    db.add(sub)
    db.commit()

    return {
        "status": "success",
        "sub_account_id": sub.id,
        "assigned_template_id": sub.assigned_template_id,
    }


# ==========================================
# 9. DISTRIBUTOR ENDPOINTS
# ==========================================


@app.get("/api/distributor/dashboard")
def get_distributor_dashboard(token: str, db: Session = Depends(get_session)):
    """Get distributor dashboard stats showing accounts created (no inventory tracking)."""
    user, user_type, distributor = get_current_distributor(token, db)

    # Get all single user accounts created by this distributor
    single_users_stmt = select(User).where(
        User.created_by_distributor_id == distributor.id
    )
    single_users = db.exec(single_users_stmt).all()

    # Get all enterprise admin accounts created by this distributor
    enterprise_admins_stmt = select(EnterpriseAdmin).where(
        EnterpriseAdmin.created_by_distributor_id == distributor.id
    )
    enterprise_admins = db.exec(enterprise_admins_stmt).all()

    # Calculate stats
    single_total = len(single_users)
    enterprise_total = len(enterprise_admins)

    # Get monthly stats (current month)
    now = datetime.utcnow()
    start_of_month = datetime(now.year, now.month, 1)

    # Accounts created this month
    single_this_month = sum(1 for u in single_users if u.created_at >= start_of_month)
    enterprise_this_month = sum(
        1 for a in enterprise_admins if a.created_at >= start_of_month
    )

    return {
        "single": {"total": single_total, "this_month": single_this_month},
        "enterprise": {"total": enterprise_total, "this_month": enterprise_this_month},
        "monthly": {"total_created": single_this_month + enterprise_this_month},
    }


# DEPRECATED: License purchasing is no longer needed
# Distributors now create accounts directly without pre-purchasing licenses
# Kept for reference only - can be removed in future cleanup
#
# @app.post("/api/distributor/purchase-licenses")
# def purchase_licenses(...):
#     ...


@app.post("/api/distributor/create-account")
def create_account_as_distributor(
    account_data: DistributorAccountCreate,
    token: str,
    db: Session = Depends(get_session),
):
    """
    Create a new user account (single or enterprise) with on-the-fly license generation.
    No inventory required - licenses are generated directly when creating accounts.
    Tracks which distributor created the account for app owner visibility.
    For existing free trial accounts: validates username match and converts to licensed.
    Sends credentials email to new/converted user with temporary password.
    """
    import re

    user, user_type, distributor = get_current_distributor(token, db)

    if account_data.account_type not in ["single", "enterprise"]:
        raise HTTPException(
            status_code=400, detail="Account type must be 'single' or 'enterprise'"
        )

    # UPGRADE FLOW: Delete old unlicensed account if upgrading
    old_account_deleted = False
    if account_data.upgrade_from_email:
        # Find the old unlicensed account
        old_user_stmt = select(User).where(
            User.email == account_data.upgrade_from_email
        )
        old_user = db.exec(old_user_stmt).first()

        if old_user:
            # Verify the old account doesn't have a valid license
            if old_user.license_id:
                old_license_stmt = select(License).where(
                    License.id == old_user.license_id
                )
                old_license = db.exec(old_license_stmt).first()
                if is_license_valid(old_license):
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot upgrade an account that already has a valid license",
                    )

            # Delete the old account
            db.delete(old_user)
            db.flush()
            old_account_deleted = True

    # Validate email format
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", account_data.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # === Handle existing free trial account conversion ===
    existing_account_converted = False
    if account_data.account_type == "single":
        # Check if email already exists in User table
        existing_user_stmt = select(User).where(User.email == account_data.email)
        existing_user = db.exec(existing_user_stmt).first()

        if existing_user:
            # Check if account already has a valid license
            if existing_user.license_id:
                existing_license_stmt = select(License).where(
                    License.id == existing_user.license_id
                )
                existing_license = db.exec(existing_license_stmt).first()
                if is_license_valid(existing_license):
                    raise HTTPException(
                        status_code=400,
                        detail="This account already has a valid license",
                    )

            # Account exists and passes validation - convert to licensed account
            existing_account_converted = True

    # Check email uniqueness across ALL user types (skip for existing account conversion)
    if not existing_account_converted:
        if db.exec(select(User).where(User.email == account_data.email)).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        if db.exec(
            select(EnterpriseAdmin).where(EnterpriseAdmin.email == account_data.email)
        ).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        if db.exec(
            select(SubAccount).where(SubAccount.email == account_data.email)
        ).first():
            raise HTTPException(status_code=400, detail="Email already registered")

    # === GENERATE LICENSE ON-THE-FLY (no inventory required) ===
    if account_data.account_type == "enterprise":
        license_key = (
            f"ENT-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"
        )
        limits = json.dumps({"max_sub_accounts": 1})
    else:  # single
        license_key = (
            f"SGL-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"
        )
        limits = json.dumps({})

    # Create license record
    license_record = License(
        license_key=license_key,
        license_type=account_data.account_type,
        limits=limits,
        is_active=True,
    )
    db.add(license_record)
    db.flush()  # Get the license ID

    # Generate temporary password if not provided
    temp_password = (
        account_data.password if account_data.password else generate_random_password(12)
    )
    password_hash = get_password_hash(temp_password)

    # === Handle existing account conversion vs new account creation ===
    if existing_account_converted:
        # Convert existing free trial account to licensed account
        existing_user.license_id = license_record.id
        existing_user.password_hash = password_hash  # Reset password
        existing_user.requires_password_change = (
            True  # Force password change on next login
        )
        existing_user.current_session_id = None  # Invalidate existing session
        existing_user.created_by_distributor_id = distributor.id  # Track distributor
        # Note: scan_count is preserved to show previous usage

        db.add(existing_user)
        db.flush()
        created_identifier = existing_user.email
        created_user_id = existing_user.id
        created_user_type = "single"
    elif account_data.account_type == "single":
        # Create new single user account
        new_user = User(
            email=account_data.email,
            password_hash=password_hash,
            requires_password_change=True,  # Force password change on first login
            license_id=license_record.id,  # Link the license to the user
            scan_count=0,  # Reset scan count for new licensed user
            created_by_distributor_id=distributor.id,  # Track which distributor created this account
        )
        db.add(new_user)
        db.flush()
        created_identifier = account_data.email
        created_user_id = new_user.id
        created_user_type = "single"
    else:  # enterprise
        # Create new enterprise admin account
        new_admin = EnterpriseAdmin(
            email=account_data.email,
            password_hash=password_hash,
            license_id=license_record.id,
            requires_password_change=True,  # Force password change on first login
            created_by_distributor_id=distributor.id,  # Track which distributor created this account
        )
        db.add(new_admin)
        db.flush()
        created_identifier = account_data.email
        created_user_id = new_admin.id
        created_user_type = "enterprise_admin"

    db.commit()

    # Send credentials email to new/converted user
    send_account_credentials_email(
        to_email=account_data.email,
        username=account_data.email,  # Use email as username in the email
        password=temp_password,
        account_type=account_data.account_type,
    )

    # Build appropriate success message
    if existing_account_converted:
        message = f"Free trial account converted to licensed account. New credentials sent to {account_data.email}"
    elif old_account_deleted:
        message = f"Account upgraded successfully. Old unlicensed account deleted. New credentials sent to {account_data.email}"
    else:
        message = f"Account created. Credentials sent to {account_data.email}"

    return {
        "status": "success",
        "account_type": account_data.account_type,
        "email": account_data.email,
        "license_key": license_record.license_key,
        "converted": existing_account_converted,
        "upgraded": old_account_deleted,
        "message": message,
    }


@app.get("/api/distributor/accounts")
def get_distributor_accounts(token: str, db: Session = Depends(get_session)):
    """Get all accounts created by this distributor."""
    user, user_type, distributor = get_current_distributor(token, db)

    # Get all single user accounts created by this distributor
    single_users = db.exec(
        select(User).where(User.created_by_distributor_id == distributor.id)
    ).all()

    # Get all enterprise admin accounts created by this distributor
    enterprise_admins = db.exec(
        select(EnterpriseAdmin).where(
            EnterpriseAdmin.created_by_distributor_id == distributor.id
        )
    ).all()

    # Build account list
    accounts = []

    for user_account in single_users:
        accounts.append(
            {
                "account_type": "single",
                "email": user_account.email,
                "created_at": user_account.created_at.isoformat(),
                "license_id": user_account.license_id,
            }
        )

    for admin_account in enterprise_admins:
        accounts.append(
            {
                "account_type": "enterprise",
                "email": admin_account.email,
                "created_at": admin_account.created_at.isoformat(),
                "license_id": admin_account.license_id,
            }
        )

    # Sort by creation date (newest first)
    accounts.sort(key=lambda x: x["created_at"], reverse=True)

    return {"accounts": accounts}


# ==========================================
# 10. APP OWNER / ADMIN ENDPOINTS
# ==========================================


@app.get("/api/admin/distributor-activity")
def get_distributor_activity(
    token: str, distributor_id: int = None, db: Session = Depends(get_session)
):
    """
    Get comprehensive distributor activity report for app owners/developers.
    Shows which distributor created which accounts and when.

    Requires app owner authentication.
    """
    # Authenticate app owner
    app_owner = get_current_app_owner(token, db)

    # Get all distributors
    all_distributors_stmt = select(Distributor).where(Distributor.is_active == True)
    all_distributors = db.exec(all_distributors_stmt).all()

    distributor_reports = []

    for dist in all_distributors:
        # Skip if filtering by specific distributor
        if distributor_id is not None and dist.id != distributor_id:
            continue

        # Get distributor user info
        if dist.user_type == "single":
            user_stmt = select(User).where(User.id == dist.user_id)
            dist_user = db.exec(user_stmt).first()
            dist_email = dist_user.email if dist_user else "Unknown"
        elif dist.user_type == "enterprise_admin":
            admin_stmt = select(EnterpriseAdmin).where(
                EnterpriseAdmin.id == dist.user_id
            )
            dist_admin = db.exec(admin_stmt).first()
            dist_email = dist_admin.email if dist_admin else "Unknown"
        else:  # sub_account
            sub_stmt = select(SubAccount).where(SubAccount.id == dist.user_id)
            dist_sub = db.exec(sub_stmt).first()
            dist_email = dist_sub.email if dist_sub else "Unknown"

        # Get all accounts created by this distributor
        single_accounts = db.exec(
            select(User).where(User.created_by_distributor_id == dist.id)
        ).all()

        enterprise_accounts = db.exec(
            select(EnterpriseAdmin).where(
                EnterpriseAdmin.created_by_distributor_id == dist.id
            )
        ).all()

        # Build account details
        created_accounts = []

        for user in single_accounts:
            created_accounts.append(
                {
                    "account_type": "single",
                    "email": user.email,
                    "created_at": user.created_at.isoformat(),
                    "license_id": user.license_id,
                    "is_active": True,  # Single users don't have is_active field
                }
            )

        for admin in enterprise_accounts:
            created_accounts.append(
                {
                    "account_type": "enterprise",
                    "email": admin.email,
                    "created_at": admin.created_at.isoformat(),
                    "license_id": admin.license_id,
                    "is_active": True,  # Enterprise admins don't have is_active field
                }
            )

        # Sort by creation date (newest first)
        created_accounts.sort(key=lambda x: x["created_at"], reverse=True)

        distributor_reports.append(
            {
                "distributor_id": dist.id,
                "distributor_email": dist_email,
                "distributor_type": dist.user_type,
                "is_active": dist.is_active,
                "created_at": dist.created_at.isoformat(),
                "total_accounts_created": len(created_accounts),
                "single_accounts_count": len(single_accounts),
                "enterprise_accounts_count": len(enterprise_accounts),
                "accounts": created_accounts,
            }
        )

    # Sort by total accounts created (descending)
    distributor_reports.sort(key=lambda x: x["total_accounts_created"], reverse=True)

    return {
        "total_distributors": len(distributor_reports),
        "distributors": distributor_reports,
    }


@app.get("/api/admin/system-stats")
def get_system_stats(token: str, db: Session = Depends(get_session)):
    """
    Get overall system statistics for app owners.
    Returns counts of users, licenses, distributors, etc.
    """
    # Authenticate app owner
    app_owner = get_current_app_owner(token, db)

    # Count all users
    total_single_users = len(db.exec(select(User)).all())
    total_enterprise_admins = len(db.exec(select(EnterpriseAdmin)).all())
    total_sub_accounts = len(db.exec(select(SubAccount)).all())
    total_distributors = len(
        db.exec(select(Distributor).where(Distributor.is_active == True)).all()
    )
    total_licenses = len(db.exec(select(License)).all())

    # Count licensed vs unlicensed users
    licensed_users = len(db.exec(select(User).where(User.license_id != None)).all())
    unlicensed_users = total_single_users - licensed_users

    # Count active licenses
    active_licenses = len(
        db.exec(select(License).where(License.is_active == True)).all()
    )

    # Get recent activity (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_single_users = len(
        db.exec(select(User).where(User.created_at >= thirty_days_ago)).all()
    )
    recent_enterprise_admins = len(
        db.exec(
            select(EnterpriseAdmin).where(EnterpriseAdmin.created_at >= thirty_days_ago)
        ).all()
    )

    return {
        "users": {
            "total_single": total_single_users,
            "licensed": licensed_users,
            "unlicensed": unlicensed_users,
            "total_enterprise_admins": total_enterprise_admins,
            "total_sub_accounts": total_sub_accounts,
            "total_all_users": total_single_users
            + total_enterprise_admins
            + total_sub_accounts,
        },
        "licenses": {"total": total_licenses, "active": active_licenses},
        "distributors": {"total_active": total_distributors},
        "recent_activity_30_days": {
            "new_single_users": recent_single_users,
            "new_enterprise_admins": recent_enterprise_admins,
            "total_new_accounts": recent_single_users + recent_enterprise_admins,
        },
    }


@app.get("/api/admin/profile")
def get_admin_profile(token: str, db: Session = Depends(get_session)):
    """Get current app owner profile information."""
    app_owner = get_current_app_owner(token, db)

    return {
        "email": app_owner.email,
        "full_name": app_owner.full_name,
        "created_at": app_owner.created_at.isoformat(),
        "last_login": app_owner.last_login.isoformat()
        if app_owner.last_login
        else None,
    }


@app.post("/api/admin/promote-distributor")
def promote_distributor(
    request: DistributorPromoteRequest, token: str, db: Session = Depends(get_session)
):
    """
    Promote a user to distributor role.
    Requires app owner authentication.
    """
    # Authenticate app owner
    app_owner = get_current_app_owner(token, db)

    # Validate user_type
    if request.user_type not in ["single", "enterprise_admin", "sub_account"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid user_type. Must be 'single', 'enterprise_admin', or 'sub_account'",
        )

    # Find user based on type
    user_obj = None
    user_id = None

    if request.user_type == "single":
        stmt = select(User).where(User.email == request.email)
        user_obj = db.exec(stmt).first()
        if user_obj:
            user_id = user_obj.id
    elif request.user_type == "enterprise_admin":
        stmt = select(EnterpriseAdmin).where(EnterpriseAdmin.email == request.email)
        user_obj = db.exec(stmt).first()
        if user_obj:
            user_id = user_obj.id
    elif request.user_type == "sub_account":
        stmt = select(SubAccount).where(SubAccount.email == request.email)
        user_obj = db.exec(stmt).first()
        if user_obj:
            user_id = user_obj.id

    if not user_obj:
        raise HTTPException(
            status_code=404,
            detail=f"User not found with email '{request.email}' for type '{request.user_type}'",
        )

    # Check if already a distributor
    check_stmt = select(Distributor).where(
        Distributor.user_id == user_id, Distributor.user_type == request.user_type
    )
    existing = db.exec(check_stmt).first()

    if existing:
        if existing.is_active:
            raise HTTPException(
                status_code=400, detail="User already has an active distributor role"
            )
        else:
            # Reactivate existing distributor role
            existing.is_active = True
            db.add(existing)
            db.commit()
            db.refresh(existing)

            return {
                "success": True,
                "message": "Distributor role reactivated successfully",
                "distributor": {
                    "id": existing.id,
                    "user_id": existing.user_id,
                    "user_type": existing.user_type,
                    "email": request.email,
                    "is_active": existing.is_active,
                    "created_at": existing.created_at.isoformat(),
                },
            }

    # Create new distributor role
    distributor = Distributor(
        user_id=user_id, user_type=request.user_type, is_active=True
    )
    db.add(distributor)
    db.commit()
    db.refresh(distributor)

    return {
        "success": True,
        "message": "User promoted to distributor successfully",
        "distributor": {
            "id": distributor.id,
            "user_id": distributor.user_id,
            "user_type": distributor.user_type,
            "email": request.email,
            "is_active": distributor.is_active,
            "created_at": distributor.created_at.isoformat(),
        },
    }


@app.post("/api/admin/revoke-distributor")
def revoke_distributor(
    request: DistributorRevokeRequest, token: str, db: Session = Depends(get_session)
):
    """
    Revoke (deactivate) a distributor role.
    Requires app owner authentication.
    """
    # Authenticate app owner
    app_owner = get_current_app_owner(token, db)

    # Validate user_type
    if request.user_type not in ["single", "enterprise_admin", "sub_account"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid user_type. Must be 'single', 'enterprise_admin', or 'sub_account'",
        )

    # Find user based on type
    user_obj = None
    user_id = None

    if request.user_type == "single":
        stmt = select(User).where(User.email == request.email)
        user_obj = db.exec(stmt).first()
        if user_obj:
            user_id = user_obj.id
    elif request.user_type == "enterprise_admin":
        stmt = select(EnterpriseAdmin).where(EnterpriseAdmin.email == request.email)
        user_obj = db.exec(stmt).first()
        if user_obj:
            user_id = user_obj.id
    elif request.user_type == "sub_account":
        stmt = select(SubAccount).where(SubAccount.email == request.email)
        user_obj = db.exec(stmt).first()
        if user_obj:
            user_id = user_obj.id

    if not user_obj:
        raise HTTPException(
            status_code=404,
            detail=f"User not found with email '{request.email}' for type '{request.user_type}'",
        )

    # Check if user has a distributor role
    check_stmt = select(Distributor).where(
        Distributor.user_id == user_id, Distributor.user_type == request.user_type
    )
    existing = db.exec(check_stmt).first()

    if not existing:
        raise HTTPException(status_code=404, detail="User is not a distributor")

    if not existing.is_active:
        raise HTTPException(
            status_code=400, detail="Distributor role is already inactive"
        )

    # Revoke distributor role
    existing.is_active = False
    db.add(existing)
    db.commit()
    db.refresh(existing)

    return {
        "success": True,
        "message": "Distributor role revoked successfully",
        "distributor": {
            "id": existing.id,
            "user_id": existing.user_id,
            "user_type": existing.user_type,
            "email": request.email,
            "is_active": existing.is_active,
            "created_at": existing.created_at.isoformat(),
        },
    }


@app.get("/api/admin/all-users")
def get_all_users(
    token: str,
    user_type: str = "all",
    only_non_distributors: bool = False,
    db: Session = Depends(get_session),
):
    """
    Get all users across all user types with their distributor status.
    Requires app owner authentication.
    """
    # Authenticate app owner
    app_owner = get_current_app_owner(token, db)

    all_users = []

    # Query single users if requested
    if user_type in ["all", "single"]:
        single_users = db.exec(select(User)).all()
        for user in single_users:
            # Check if user is a distributor
            dist_stmt = select(Distributor).where(
                Distributor.user_id == user.id, Distributor.user_type == "single"
            )
            distributor = db.exec(dist_stmt).first()

            is_distributor = distributor is not None
            distributor_active = distributor.is_active if distributor else None

            # Apply non-distributor filter
            if only_non_distributors and is_distributor and distributor_active:
                continue

            all_users.append(
                {
                    "id": user.id,
                    "email": user.email,
                    "user_type": "single",
                    "created_at": user.created_at.isoformat(),
                    "is_distributor": is_distributor,
                    "distributor_active": distributor_active,
                    "license_id": user.license_id,
                }
            )

    # Query enterprise admins if requested
    if user_type in ["all", "enterprise_admin"]:
        enterprise_admins = db.exec(select(EnterpriseAdmin)).all()
        for admin in enterprise_admins:
            # Check if admin is a distributor
            dist_stmt = select(Distributor).where(
                Distributor.user_id == admin.id,
                Distributor.user_type == "enterprise_admin",
            )
            distributor = db.exec(dist_stmt).first()

            is_distributor = distributor is not None
            distributor_active = distributor.is_active if distributor else None

            # Apply non-distributor filter
            if only_non_distributors and is_distributor and distributor_active:
                continue

            all_users.append(
                {
                    "id": admin.id,
                    "email": admin.email,
                    "user_type": "enterprise_admin",
                    "created_at": admin.created_at.isoformat(),
                    "is_distributor": is_distributor,
                    "distributor_active": distributor_active,
                    "license_id": admin.license_id,
                }
            )

    # Query sub-accounts if requested
    if user_type in ["all", "sub_account"]:
        sub_accounts = db.exec(select(SubAccount)).all()
        for sub in sub_accounts:
            # Check if sub-account is a distributor
            dist_stmt = select(Distributor).where(
                Distributor.user_id == sub.id, Distributor.user_type == "sub_account"
            )
            distributor = db.exec(dist_stmt).first()

            is_distributor = distributor is not None
            distributor_active = distributor.is_active if distributor else None

            # Apply non-distributor filter
            if only_non_distributors and is_distributor and distributor_active:
                continue

            all_users.append(
                {
                    "id": sub.id,
                    "email": sub.email,
                    "user_type": "sub_account",
                    "created_at": sub.created_at.isoformat(),
                    "is_distributor": is_distributor,
                    "distributor_active": distributor_active,
                    "admin_id": sub.admin_id,
                }
            )

    # Sort by creation date (newest first)
    all_users.sort(key=lambda x: x["created_at"], reverse=True)

    return {"total_users": len(all_users), "users": all_users}
