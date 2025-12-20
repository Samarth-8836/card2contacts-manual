from typing import Optional
from sqlmodel import Field, SQLModel, create_engine, Session, select
from passlib.context import CryptContext

# ==============================================================================
# 1. Database Setup
# ==============================================================================
DATABASE_URL = "postgresql://admin:securepassword@localhost:5432/scanner_prod"
engine = create_engine(DATABASE_URL)

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
    current_session_id: Optional[str] = Field(default=None) 
    
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