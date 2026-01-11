# DigiCard Enterprise - Technical Architecture Document

**Version:** 1.0
**Date:** January 11, 2026
**Document Type:** System Architecture & Implementation Guide
**Target Audience:** Senior Software Architects

---

## Document Navigation

1. [Executive Summary](#1-executive-summary)
2. [Technology Stack](#2-technology-stack)
3. [System Architecture](#3-system-architecture)
4. [Data Model & Database Schema](#4-data-model--database-schema)
5. [API Architecture](#5-api-architecture)
6. [Authentication & Authorization](#6-authentication--authorization)
7. [Key Integrations](#7-key-integrations)
8. [Business Logic Flows](#8-business-logic-flows)
9. [Frontend Architecture](#9-frontend-architecture)
10. [Configuration Management](#10-configuration-management)
11. [Feature Implementation Guide](#11-feature-implementation-guide)
12. [Deployment Architecture](#12-deployment-architecture)
13. [Security Considerations](#13-security-considerations)
14. [Appendix](#14-appendix)

---

## 1. Executive Summary

### 1.1 Project Overview

**DigiCard Enterprise** is a B2B2C digital business card scanning and contact management platform that transforms physical business cards into structured, actionable digital data through AI-powered OCR and automatic Google Workspace integration.

### 1.2 Core Value Proposition

- **Instant Digitization**: AI-powered OCR converts physical cards to digital contacts in seconds
- **Zero Manual Entry**: Automatic data extraction eliminates manual typing
- **Enterprise Scalability**: Multi-user team accounts with centralized management
- **Automated Outreach**: Built-in email automation for immediate follow-up
- **Distributor Network**: B2B2C model enabling resellers to provision accounts

### 1.3 System Type

- **Application Type**: Progressive Web Application (PWA)
- **Architecture**: Client-Server (REST API + SPA)
- **Deployment Model**: Containerized (Docker) with PostgreSQL database
- **Authentication Flow**: JWT-based with OTP verification

### 1.4 Primary User Types

1. **Single Users**: Individual professionals with personal Google accounts
2. **Enterprise Admins**: Team managers with multiple sub-accounts
3. **Sub-Accounts**: Team members with limited permissions
4. **Distributors**: Resellers who create and manage customer accounts
5. **App Owners**: Platform administrators with system-wide visibility

---

## 2. Technology Stack

### 2.1 Backend Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Framework** | FastAPI | 0.115.5 | REST API framework |
| **Server** | Uvicorn | 0.32.1 | ASGI server |
| **ORM** | SQLModel | 0.0.22 | Database ORM (Pydantic + SQLAlchemy) |
| **Database** | PostgreSQL | 15 | Primary data store |
| **Authentication** | python-jose | 3.3.0 | JWT token handling |
| **Password Hashing** | passlib | 1.7.4 | bcrypt password hashing |
| **Configuration** | pydantic-settings | 2.6.1 | Environment-based configuration |

### 2.2 AI/ML Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **OCR Provider** | Mistral AI | Text extraction from images |
| **AI Orchestrator** | LiteLLM | Unified interface for multiple LLM providers |
| **Primary LLM** | Groq (Llama 3.1) | Fast, affordable AI for data structuring |
| **Alternative LLM** | Google Gemini | Structured vCard generation |
| **Image Processing** | OpenCV, Pillow | Image manipulation and preprocessing |

### 2.3 Google Integration Stack

| Component | Google Service | Purpose |
|-----------|---------------|---------|
| **Authentication** | Google OAuth 2.0 | User authentication |
| **Data Storage** | Google Sheets API | Contact data storage |
| **File Storage** | Google Drive API | Business card images, attachments |
| **Email Sending** | Gmail API | Automated follow-up emails |
| **Required Scopes** | - userinfo.email<br>- userinfo.profile<br>- drive<br>- gmail.modify<br>- gmail.send | Full workspace integration |

### 2.4 Frontend Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Language** | Vanilla JavaScript | No framework dependencies |
| **Type** | Progressive Web App (PWA) | Installable, app-like experience |
| **Camera** | HTML5 MediaDevices API | Device camera access |
| **HTTP Client** | Fetch API | API communication |
| **State Management** | Global state object | Client-side state |

### 2.5 DevOps & Deployment

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Containerization** | Docker | Application packaging |
| **Orchestration** | Docker Compose | Multi-container deployment |
| **Email Service** | SMTP (Hostinger) | Transactional emails (OTP, credentials) |
| **Environment** | Linux/Windows | Cross-platform support |

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Single User  │  │ Enterprise   │  │ Sub-Account  │  │ App Owner    │   │
│  │   PWA        │  │ Admin PWA    │  │   PWA        │  │ Dashboard    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │ HTTPS / REST API
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API GATEWAY LAYER                                │
│                    FastAPI Application (Uvicorn)                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CORS Middleware │ Auth Middleware │ Request Validation │ Error   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Database   │  │   AI/OCR     │  │  External    │
│   Service    │  │   Service    │  │  Services    │
│              │  │              │  │              │
│ PostgreSQL   │  │ Mistral OCR  │  │ Google APIs  │
│              │  │ Groq/Gemini  │  │ SMTP Email   │
└──────────────┘  └──────────────┘  └──────────────┘
```

### 3.2 Component Interaction Flow

#### 3.2.1 Business Card Scanning Flow

```
1. User scans card via PWA
   ↓
2. Image uploaded to backend (/api/scan/ocr)
   ↓
3. Backend calls Mistral OCR API
   ↓
4. OCR returns raw text
   ↓
5. Backend calls LLM (Groq/Gemini) to structure text into vCard format
   ↓
6. User reviews/edits extracted data
   ↓
7. User saves contact (/api/scan/save)
   ↓
8. Contact appended to Google Sheets
   ↓
9. If auto-email enabled: Email sent via Gmail API
   ↓
10. If bulk mode: Image staged, batch processed later
```

#### 3.2.2 Authentication Flow

```
1. User enters email/username and password
   ↓
2. POST /api/auth/login/initiate
   ↓
3. Backend validates credentials
   ↓
4. Backend generates 6-digit OTP
   ↓
5. Backend sends OTP via SMTP to user's email
   ↓
6. Frontend shows OTP input field
   ↓
7. User enters OTP
   ↓
8. POST /api/auth/login/verify
   ↓
9. Backend verifies OTP (expires in 5 min, max 5 attempts)
   ↓
10. Backend generates JWT token
    ↓
11. Backend invalidates all previous sessions (single-device enforcement)
    ↓
12. JWT returned to frontend
    ↓
13. Frontend stores token in localStorage
    ↓
14. Token sent with all subsequent requests (Authorization header)
```

### 3.3 Key Design Patterns

| Pattern | Implementation | Purpose |
|---------|---------------|---------|
| **Factory Pattern** | OCRProviderFactory | Pluggable OCR providers |
| **Repository Pattern** | Database session management | Data access abstraction |
| **Middleware Pattern** | FastAPI middleware | Cross-cutting concerns (CORS, auth) |
| **Singleton Pattern** | OCR provider instances | Resource optimization |
| **JWT Session** | Token-based auth with session ID | Stateless authentication with device tracking |

---

## 4. Data Model & Database Schema

### 4.1 Entity Relationship Diagram (ERD)

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     User        │       │ EnterpriseAdmin │       │   SubAccount    │
│─────────────────│       │─────────────────│       │─────────────────│
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ email (unique)  │       │ email (unique)  │       │ email (unique)  │
│ password_hash   │       │ password_hash   │       │ password_hash   │
│ current_session │       │ current_session │       │ current_session │
│ requires_pwd_ch │       │ requires_pwd_ch │       │ is_active       │
│ license_id (FK) │       │ license_id (FK) │───────►│ admin_id (FK)   │
│ scan_count      │       │ requires_pwd_ch │       │ sheet_name      │
│ google_*        │       │ google_*        │       │ assigned_tmp_id │
│ email_feature   │       │ email_feature   │       └─────────────────┘
└────────┬────────┘       │ created_by_d_id │
         │                └────────┬────────┘
         │                         │
         │ created_by_d_id         │ created_by_d_id
         │                         │
┌────────▼────────────────────────▼────────────────────────────────┐
│                     Distributor                                   │
│────────────────────────────────────────────────────────────────────│
│ id (PK)                                                          │
│ user_id                                                          │
│ user_type (single/enterprise_admin/sub_account)                 │
│ is_active                                                        │
└────────┬──────────────────────────────────────────────────────────┘
         │
         │ distributor_id
         ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│DistributorLicense│       │DistributorPurchase│     │    License       │
│─────────────────│       │─────────────────│       │─────────────────│
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ distributor_id  │       │ distributor_id  │       │ license_key     │
│ license_id (FK) │──────►│ license_type    │       │ license_type    │
│ license_type    │       │ count           │       │ limits (JSON)   │
│ is_assigned     │       │ purchased_at    │       │ is_active       │
│ assigned_to_*   │       └─────────────────┘       └─────────────────┘
│ assigned_at     │
└─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│     AppOwner    │       │    OTPRecord    │
│─────────────────│       │─────────────────│
│ id (PK)         │       │ id (PK)         │
│ email (unique)  │       │ identifier      │
│ password_hash   │       │ user_type       │
│ full_name       │       │ user_id         │
│ is_active       │       │ otp_code        │
│ current_session │       │ expires_at      │
│ last_login      │       │ attempts        │
└─────────────────┘       │ pending_session │
                          └─────────────────┘
```

### 4.2 Detailed Table Schemas

#### 4.2.1 User Table

Single-user accounts for individual professionals.

```sql
CREATE TABLE user (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    current_session_id VARCHAR,  -- Single-device enforcement
    requires_password_change BOOLEAN DEFAULT FALSE,  -- Force password change on first login

    -- License tracking
    license_id INTEGER REFERENCES license(id),
    scan_count INTEGER DEFAULT 0,  -- For unlicensed users (max 4)

    -- Distributor tracking
    created_by_distributor_id INTEGER REFERENCES distributor(id),

    -- Google integration
    google_connected BOOLEAN DEFAULT FALSE,
    google_spreadsheet_id VARCHAR,
    google_access_token VARCHAR,
    google_refresh_token VARCHAR,
    google_token_uri VARCHAR DEFAULT 'https://oauth2.googleapis.com/token',
    google_client_id VARCHAR,
    google_client_secret VARCHAR,
    email_feature_enabled BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Business Rules:**
- Free tier users limited to 4 scans (configurable)
- Licensed users have unlimited scans for 1 year
- Google tokens stored encrypted (implementation detail)
- Session ID tracks active device

#### 4.2.2 EnterpriseAdmin Table

Team managers with sub-account capabilities.

```sql
CREATE TABLE enterpriseadmin (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    current_session_id VARCHAR,
    requires_password_change BOOLEAN DEFAULT FALSE,

    -- License linking
    license_id INTEGER REFERENCES license(id) NOT NULL,

    -- Distributor tracking
    created_by_distributor_id INTEGER REFERENCES distributor(id),

    -- Google integration (for admin's own scanning)
    google_connected BOOLEAN DEFAULT FALSE,
    google_spreadsheet_id VARCHAR,
    google_access_token VARCHAR,
    google_refresh_token VARCHAR,
    google_token_uri VARCHAR DEFAULT 'https://oauth2.googleapis.com/token',
    google_client_id VARCHAR,
    google_client_secret VARCHAR,
    email_feature_enabled BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Business Rules:**
- Must have an active enterprise license
- License includes `max_sub_accounts` limit (stored in License.limits JSON)
- Creates/manages sub-accounts
- Google account used for all sub-account operations

#### 4.2.3 SubAccount Table

Team member accounts with limited permissions.

```sql
CREATE TABLE subaccount (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,  -- Treated as username
    password_hash VARCHAR NOT NULL,
    admin_id INTEGER REFERENCES enterpriseadmin(id) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    current_session_id VARCHAR,

    -- Google integration (uses admin's credentials)
    sheet_name VARCHAR,  -- Sheet name format: "SubAccount_{username}"

    -- Email template assignment
    assigned_template_id VARCHAR,  -- Row ID from admin's Email_Templates sheet

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Business Rules:**
- Cannot link their own Google account (uses admin's)
- Cannot create email templates (uses assigned template)
- Contacts save to dedicated sheet in admin's spreadsheet
- Deactivation by admin blocks login immediately

#### 4.2.4 License Table

License management for both single and enterprise accounts.

```sql
CREATE TABLE license (
    id SERIAL PRIMARY KEY,
    license_key VARCHAR UNIQUE NOT NULL,
    license_type VARCHAR DEFAULT 'enterprise',  -- "single" or "enterprise"
    limits VARCHAR DEFAULT '{"max_sub_accounts": 5}',  -- JSON string
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Business Rules:**
- Valid for 1 year from creation
- Single licenses: unlimited scans for one user
- Enterprise licenses: unlimited scans + sub-accounts
- Limits JSON stores seat count for enterprise licenses

#### 4.2.5 Distributor Table

Reseller role assignment.

```sql
CREATE TABLE distributor (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,  -- ID from User, EnterpriseAdmin, or SubAccount
    user_type VARCHAR NOT NULL,  -- "single", "enterprise_admin", "sub_account"
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Business Rules:**
- Can be assigned to any user type
- Distributors create customer accounts instantly
- All accounts permanently linked to creating distributor
- Used for analytics and commission tracking

#### 4.2.6 DistributorLicense Table

License ownership and assignment tracking.

```sql
CREATE TABLE distributorlicense (
    id SERIAL PRIMARY KEY,
    distributor_id INTEGER REFERENCES distributor(id) NOT NULL,
    license_id INTEGER REFERENCES license(id) NOT NULL,
    license_type VARCHAR NOT NULL,  -- Denormalized: "single" or "enterprise"
    is_assigned BOOLEAN DEFAULT FALSE,
    assigned_to_user_id INTEGER,
    assigned_to_user_type VARCHAR,  -- "single" or "enterprise_admin"
    assigned_at TIMESTAMP,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Business Rules:**
- Tracks which distributor owns which licenses
- Marks when license is assigned to customer
- Used for distributor analytics and reporting

#### 4.2.7 OTPRecord Table

One-time password tracking for login verification.

```sql
CREATE TABLE otprecord (
    id SERIAL PRIMARY KEY,
    identifier VARCHAR NOT NULL,  -- Email or username
    user_type VARCHAR NOT NULL,  -- "single", "enterprise_admin", "sub_account"
    user_id INTEGER NOT NULL,
    otp_code VARCHAR NOT NULL,  -- 6-digit code
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    attempts INTEGER DEFAULT 0,  -- Max 5 attempts
    pending_session_id VARCHAR NOT NULL  -- UUID for tracking login attempt
);
```

**Business Rules:**
- OTP expires after 5 minutes
- Max 5 verification attempts, then lockout
- Used for both single users and sub-accounts
- Sub-account OTP sent to enterprise admin's email

#### 4.2.8 AppOwner Table

Platform administrator accounts.

```sql
CREATE TABLE appowner (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    full_name VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    current_session_id VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);
```

**Business Rules:**
- Separate user type from regular users
- Full platform access via admin endpoints
- Used for system monitoring and analytics

### 4.3 Database Indexes

Critical indexes for performance:

```sql
-- User lookups
CREATE INDEX idx_user_email ON user(email);
CREATE INDEX idx_user_license ON user(license_id);
CREATE INDEX idx_user_distributor ON user(created_by_distributor_id);

-- Enterprise lookups
CREATE INDEX idx_enterprise_email ON enterpriseadmin(email);
CREATE INDEX idx_enterprise_license ON enterpriseadmin(license_id);
CREATE INDEX idx_enterprise_distributor ON enterpriseadmin(created_by_distributor_id);

-- Sub-account lookups
CREATE INDEX idx_subaccount_email ON subaccount(email);
CREATE INDEX idx_subaccount_admin ON subaccount(admin_id);

-- License lookups
CREATE INDEX idx_license_key ON license(license_key);

-- OTP lookups
CREATE INDEX idx_otp_identifier ON otprecord(identifier);
CREATE INDEX idx_otp_expires ON otprecord(expires_at);

-- Distributor lookups
CREATE INDEX idx_distributor_user ON distributor(user_id);
CREATE INDEX idx_distributorlicense_distributor ON distributorlicense(distributor_id);
```

---

## 5. API Architecture

### 5.1 API Overview

The API follows RESTful principles with JWT-based authentication. All endpoints except authentication require a valid JWT token.

**Base URL**: `https://yourdomain.com/api`

**Authentication**: `Authorization: Bearer <token>` header or `?token=<token>` query param

### 5.2 Authentication Endpoints

#### POST /api/auth/login/initiate
Initiate login with email/username and password.

**Request:**
```json
{
  "identifier": "user@example.com",
  "password": "userpassword"
}
```

**Response:**
```json
{
  "status": "otp_sent",
  "user_type": "single",
  "otp_sent_to": "u***@example.com",
  "session_token": "uuid-here",
  "message": "OTP sent to your email"
}
```

**Logic:**
1. Validate credentials across User, EnterpriseAdmin, SubAccount tables
2. Check if password change required (distributor-created accounts)
3. Generate 6-digit OTP
4. Send OTP via SMTP
5. For sub-accounts, send OTP to enterprise admin's email
6. Return session token for OTP verification step

#### POST /api/auth/login/verify
Verify OTP and complete authentication.

**Request:**
```json
{
  "session_token": "uuid-here",
  "otp_code": "123456"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbG...",
  "token_type": "bearer",
  "user_type": "single",
  "user_email": "user@example.com",
  "requires_password_change": false
}
```

**Logic:**
1. Validate OTP (code, expiration, max attempts)
2. Generate JWT token with 30-day expiration
3. Update `current_session_id` in user table (single-device enforcement)
4. Include user metadata in JWT payload

#### POST /api/auth/logout
Logout and invalidate session.

**Request:**
```json
{
  "token": "jwt-token"
}
```

**Response:**
```json
{
  "message": "Logged out successfully"
}
```

#### POST /api/auth/password-reset
Request password reset (new password generated and sent via email).

**Request:**
```json
{
  "email": "user@example.com"
}
```

#### POST /api/auth/change-password
Change password (requires current password).

**Request:**
```json
{
  "current_password": "oldpass",
  "new_password": "newpass"
}
```

### 5.3 User Management Endpoints

#### POST /api/auth/register
Register new single-user account.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Logic:**
- Sends verification email
- Grants 4 free scans
- No license required initially

#### GET /api/user/profile
Get current user profile.

**Response:**
```json
{
  "email": "user@example.com",
  "user_type": "single",
  "google_connected": false,
  "email_feature_enabled": false,
  "scan_count": 2,
  "scans_remaining": 2,
  "license_status": "none"
}
```

#### GET /api/user/scan-status
Check scan limits and license status.

**Response:**
```json
{
  "scan_count": 2,
  "scans_remaining": 2,
  "is_licensed": false,
  "license_expires_at": null,
  "free_tier_limit": 4
}
```

### 5.4 Google Integration Endpoints

#### GET /api/auth/google
Initiate Google OAuth flow.

**Redirects to:** Google OAuth consent screen

**Required Scopes:**
- `openid`
- `https://www.googleapis.com/auth/userinfo.email`
- `https://www.googleapis.com/auth/userinfo.profile`
- `https://www.googleapis.com/auth/drive`
- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/gmail.send`

#### GET /api/auth/google/callback
OAuth callback handler.

**Query Params:**
- `code`: OAuth authorization code
- `state`: CSRF token (optional)

**Process:**
1. Exchange code for access/refresh tokens
2. Verify all required scopes granted
3. Create spreadsheet in Google Drive if not exists
4. Create folder structure:
   - `DigiCard/Contact Spreadsheets`
   - `DigiCard/Card Images`
   - `DigiCard/Bulk Staging`
5. Store tokens in user table
6. Redirect to frontend with success/error status

#### GET /api/user/google/status
Check Google connection status.

**Response:**
```json
{
  "google_connected": true,
  "google_spreadsheet_id": "sheet-id-here",
  "missing_scopes": [],
  "email_feature_enabled": true
}
```

#### DELETE /api/user/google/unlink
Unlink Google account.

**Response:**
```json
{
  "message": "Google account unlinked successfully"
}
```

### 5.5 Business Card Scanning Endpoints

#### POST /api/scan/ocr
Perform OCR on uploaded business card image.

**Request:** `multipart/form-data`
```
image: <file>
```

**Response:**
```json
{
  "raw_text": "Extracted text from card...",
  "structured_data": {
    "fn": ["John Doe"],
    "org": "Example Corp",
    "title": "CEO",
    "tel": ["+1-555-1234"],
    "email": ["john@example.com"],
    "url": ["https://example.com"],
    "adr": ["123 Main St"],
    "cat": ["Technology"],
    "notes": "Met at conference"
  }
}
```

**Process:**
1. Receive image file
2. Call Mistral OCR API
3. Extract raw text
4. Call LLM (Groq/Gemini) to structure text into vCard format
5. Return both raw and structured data

#### POST /api/scan/save
Save scanned contact.

**Request:**
```json
{
  "fn": ["John Doe"],
  "org": "Example Corp",
  "title": "CEO",
  "tel": ["+1-555-1234"],
  "email": ["john@example.com"],
  "url": ["https://example.com"],
  "adr": ["123 Main St"],
  "cat": ["Technology"],
  "notes": "Met at conference"
}
```

**Response:**
```json
{
  "message": "Contact saved successfully",
  "google_sheet_updated": true,
  "email_sent": true,
  "scan_count": 3
}
```

**Process:**
1. Validate contact data
2. Increment scan count (for unlicensed users)
3. Append to Google Sheets
4. If auto-email enabled, send email via Gmail API
5. Return confirmation

#### POST /api/scan/bulk/stage
Stage business card images for bulk processing.

**Request:** `multipart/form-data`
```
images: <files>
```

**Response:**
```json
{
  "staged_count": 5,
  "total_staged": 15,
  "bulk_mode": true
}
```

**Process:**
1. Upload images to Google Drive staging folder
2. Track staged images in internal Google Sheet
3. Return count of staged images

#### POST /api/scan/bulk/submit
Submit staged images for batch processing.

**Response:**
```json
{
  "message": "Bulk processing started",
  "total_images": 15,
  "estimated_time": "5-10 minutes"
}
```

**Process:**
1. Trigger async background task
2. Process each image sequentially
3. For each card: OCR → LLM structuring → Save to Google Sheets → Send email
4. Update status in bulk tracking sheet

### 5.6 Email Template Endpoints

#### GET /api/templates
Fetch all email templates from Google Sheets.

**Response:**
```json
{
  "templates": [
    {
      "row_id": "1",
      "subject": "Nice to meet you!",
      "body": "Hi {name},...",
      "has_attachments": true
    }
  ]
}
```

**Location:** Templates stored in Google Sheets, sheet named "Email_Templates"

#### POST /api/templates
Create new email template.

**Request:**
```json
{
  "subject": "Follow-up from event",
  "body": "<p>Hi {name}...</p>",
  "attachments": [
    {
      "filename": "brochure.pdf",
      "data": "base64-encoded-file",
      "size": 1024000
    }
  ]
}
```

**Process:**
1. Upload attachments to Google Drive (Email_Template_Attachments folder)
2. Add row to Email_Templates sheet
3. Include attachment IDs in row

#### POST /api/templates/set-active
Set active template for auto-emailing.

**Request:**
```json
{
  "template_row_id": "1"
}
```

### 5.7 Enterprise Management Endpoints

#### POST /api/enterprise/subaccounts
Create new sub-account (enterprise admin only).

**Request:**
```json
{
  "email": "teamuser",
  "password": "password123"
}
```

**Response:**
```json
{
  "message": "Sub-account created",
  "sub_account_id": 5,
  "sheet_name": "SubAccount_teamuser"
}
```

**Logic:**
1. Check seat limit (max_sub_accounts in license)
2. Create sub-account record
3. Create dedicated sheet in admin's spreadsheet
4. Return credentials

#### PUT /api/enterprise/subaccounts/{id}
Update sub-account.

**Request:**
```json
{
  "email": "newusername",
  "password": "newpass"
}
```

#### PUT /api/enterprise/subaccounts/{id}/activate
Activate sub-account.

#### PUT /api/enterprise/subaccounts/{id}/deactivate
Deactivate sub-account (blocks login).

#### GET /api/enterprise/subaccounts
List all sub-accounts.

**Response:**
```json
{
  "sub_accounts": [
    {
      "id": 5,
      "email": "teamuser",
      "is_active": true,
      "sheet_name": "SubAccount_teamuser",
      "assigned_template_id": "1"
    }
  ]
}
```

#### GET /api/enterprise/export/{type}
Export contacts to Excel.

**Types:**
- `own`: Admin's own contacts
- `sub:{id}`: Specific sub-account's contacts
- `combined`: All contacts (admin + all sub-accounts)

**Response:** Excel file download

### 5.8 Distributor Endpoints

#### POST /api/distributor/create-account
Create new customer account (distributor only).

**Request:**
```json
{
  "account_type": "single",  // or "enterprise"
  "customer_email": "customer@example.com",
  "license_type": "single",  // or "enterprise"
  "max_sub_accounts": 5  // Only for enterprise
}
```

**Response:**
```json
{
  "message": "Account created",
  "account_type": "single",
  "email": "customer@example.com",
  "temporary_password": "tempPass123",
  "license_key": "LICENSE-KEY-123"
}
```

**Process:**
1. Generate license key
2. Create license in database
3. Create user account
4. Link to distributor (created_by_distributor_id)
5. Generate random password
6. Send credentials via email
7. Create DistributorLicense record

#### GET /api/distributor/accounts
List all accounts created by distributor.

**Response:**
```json
{
  "accounts": [
    {
      "account_type": "single",
      "email": "customer@example.com",
      "created_at": "2024-01-15T10:00:00Z",
      "license_key": "LICENSE-KEY-123"
    }
  ]
}
```

### 5.9 Admin Dashboard Endpoints

#### POST /api/admin/login
App owner authentication.

**Request:**
```json
{
  "email": "admin@example.com",
  "password": "adminpass"
}
```

**Response:**
```json
{
  "access_token": "jwt-token",
  "token_type": "bearer",
  "user_type": "app_owner",
  "full_name": "John Doe"
}
```

#### GET /api/admin/system-stats
Get platform-wide statistics.

**Response:**
```json
{
  "users": {
    "total_single": 1000,
    "licensed": 850,
    "unlicensed": 150,
    "total_enterprise_admins": 50,
    "total_sub_accounts": 200,
    "total_all_users": 1250
  },
  "licenses": {
    "total": 900,
    "active": 875
  },
  "distributors": {
    "total_active": 15
  },
  "recent_activity_30_days": {
    "new_single_users": 120,
    "new_enterprise_admins": 14,
    "total_new_accounts": 134
  }
}
```

#### GET /api/admin/distributor-activity
Get detailed distributor performance data.

**Query Params:**
- `token`: JWT token (required)
- `distributor_id`: Optional filter by specific distributor

**Response:**
```json
{
  "total_distributors": 15,
  "distributors": [
    {
      "distributor_id": 1,
      "distributor_email": "dist@example.com",
      "distributor_type": "enterprise_admin",
      "is_active": true,
      "created_at": "2024-01-10T08:00:00Z",
      "total_accounts_created": 45,
      "single_accounts_count": 30,
      "enterprise_accounts_count": 15,
      "accounts": [
        {
          "account_type": "single",
          "email": "user1@example.com",
          "created_at": "2024-01-15T14:30:00Z",
          "license_id": 123,
          "is_active": true
        }
      ]
    }
  ]
}
```

---

## 6. Authentication & Authorization

### 6.1 Authentication Flow Diagram

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ 1. POST /api/auth/login/initiate
       │    {identifier, password}
       ▼
┌─────────────────┐
│   API Gateway   │
└──────┬──────────┘
       │ 2. Validate credentials
       ▼
┌─────────────────┐
│   Database      │  Check: User / EnterpriseAdmin / SubAccount
└──────┬──────────┘
       │ 3. Generate 6-digit OTP
       │ 4. Store in OTPRecord
       ▼
┌─────────────────┐
│   SMTP Service  │  Send OTP to user's email
└──────┬──────────┘
       │ 5. Return session_token
       ▼
┌─────────────┐
│   Client    │  Show OTP input
└──────┬──────┘
       │ 6. POST /api/auth/login/verify
       │    {session_token, otp_code}
       ▼
┌─────────────────┐
│   API Gateway   │
└──────┬──────────┘
       │ 7. Verify OTP (code, expiry, attempts)
       ▼
┌─────────────────┐
│   Database      │  Update current_session_id
└──────┬──────────┘
       │ 8. Generate JWT
       │    Payload: {user_id, user_type, session_id}
       ▼
┌─────────────┐
│   Client    │  Store JWT in localStorage
└─────────────┘

All subsequent requests:
Client → API Gateway (with Authorization: Bearer <token>)
API Gateway → Verify JWT signature and session_id match
```

### 6.2 JWT Token Structure

**Header:**
```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**Payload:**
```json
{
  "sub": "user-id",
  "user_type": "single",  // "enterprise_admin" | "sub_account" | "app_owner"
  "email": "user@example.com",
  "sid": "current-session-id",
  "exp": 1737033600,
  "iat": 1734441600
}
```

**Expiration:** 30 days (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)

### 6.3 Single-Device Enforcement

**Mechanism:**
1. Each user has `current_session_id` field in database
2. JWT token includes `sid` (session ID) claim
3. On each request, verify: `token.sid === user.current_session_id`
4. When user logs in, generate new session ID and update database
5. Previous sessions immediately invalidated

**Implementation:**
```python
def get_current_user(token: str, db: Session):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    user = db.get(User, payload["sub"])
    if user.current_session_id != payload["sid"]:
        raise HTTPException(401, "Session expired - logged in from another device")
    return user
```

### 6.4 Authorization Matrix

| Endpoint | Single User | Enterprise Admin | Sub-Account | Distributor | App Owner |
|----------|-------------|------------------|-------------|-------------|-----------|
| /api/scan/* | ✓ | ✓ | ✓ | ✓ | ✗ |
| /api/user/* | ✓ (own) | ✓ (own) | ✗ | ✓ (own) | ✗ |
| /api/enterprise/* | ✗ | ✓ | ✗ | ✗ | ✗ |
| /api/distributor/* | ✗ | ✗ | ✗ | ✓ | ✗ |
| /api/admin/* | ✗ | ✗ | ✗ | ✗ | ✓ |

### 6.5 OTP Security Rules

| Rule | Value |
|------|-------|
| OTP Length | 6 digits |
| OTP Expiration | 5 minutes |
| Max Attempts | 5 |
| Lockout Duration | Configured by admin |
| Delivery Method | SMTP email |
| Sub-Account OTP Sent To | Enterprise admin's email |

---

## 7. Key Integrations

### 7.1 Google Workspace Integration

#### 7.1.1 OAuth 2.0 Flow

**Step 1: Initiate OAuth**
```
GET /api/auth/google
  ↓
Redirect to: https://accounts.google.com/o/oauth2/v2/auth?
  client_id={CLIENT_ID}&
  redirect_uri={REDIRECT_URI}&
  scope={SCOPES}&
  response_type=code
```

**Step 2: User Consent**
- User grants permissions
- Google redirects with authorization code

**Step 3: Exchange Code for Tokens**
```python
flow = Flow.from_client_config(
    client_config,
    scopes=SCOPES,
    redirect_uri=REDIRECT_URI
)
flow.fetch_token(code=authorization_code)
```

**Step 4: Store Tokens**
```python
user.google_access_token = flow.credentials.token
user.google_refresh_token = flow.credentials.refresh_token
user.google_client_id = CLIENT_ID
user.google_client_secret = CLIENT_SECRET
user.google_token_uri = "https://oauth2.googleapis.com/token"
```

**Step 5: Token Refresh**
```python
creds = Credentials(
    token=user.google_access_token,
    refresh_token=user.google_refresh_token,
    token_uri=user.google_token_uri,
    client_id=user.google_client_id,
    client_secret=user.google_client_secret
)
creds.refresh(Request())  # Automatically refreshes if expired
```

#### 7.1.2 Google Sheets Structure

**Folder Structure in Google Drive:**
```
My Drive/
└── DigiCard/
    ├── Contact Spreadsheets/
    │   └── DigiCard_Contacts.xlsx
    │       ├── Sheet1 (Admin's own contacts)
    │       ├── SubAccount_user1
    │       ├── SubAccount_user2
    │       └── Email_Templates
    │           └── Column headers: [row_id, subject, body, attachment_ids, created_at]
    ├── Card Images/
    └── Bulk Staging/
```

**Contact Sheet Columns:**
```
Column A: Contact Name
Column B: Business Name
Column C: Contact Numbers
Column D: Job Title
Column E: Emails
Column F: Websites
Column G: Address
Column H: Import Source (Single/Bulk)
Column I: Business Category
Column J: AI Notes
Column K: Scan Date
```

**Email Templates Sheet Columns:**
```
Column A: row_id (timestamp)
Column B: subject
Column C: body (HTML)
Column D: attachment_ids (comma-separated)
Column E: created_at
```

#### 7.1.3 Google Sheets Operations

**Append Contact:**
```python
def append_to_sheet(spreadsheet_id, sheet_name, contact_data):
    service = build('sheets', 'v4', credentials=creds)
    values = [[
        contact_data['fn'][0] if contact_data['fn'] else '',
        contact_data.get('org', ''),
        ', '.join(contact_data.get('tel', [])),
        contact_data.get('title', ''),
        ', '.join(contact_data.get('email', [])),
        ', '.join(contact_data.get('url', [])),
        ', '.join(contact_data.get('adr', [])),
        'Single',
        ', '.join(contact_data.get('cat', [])),
        contact_data.get('notes', ''),
        datetime.now().isoformat()
    ]]

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={'values': values}
    ).execute()
```

**Export as Excel:**
```python
def export_sheet_as_excel(spreadsheet_id, sheet_name):
    service = build('drive', 'v3', credentials=creds)

    # Request export
    request = service.files().export_media(
        fileId=spreadsheet_id,
        mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

    # Download file
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()

    fh.seek(0)
    return fh
```

#### 7.1.4 Gmail Email Sending

**Send Email:**
```python
def send_gmail(creds, to_email, subject, body, attachments=None):
    service = build('gmail', 'v1', credentials=creds)

    # Create message
    message = MIMEMultipart()
    message['to'] = to_email
    message['subject'] = subject
    message.attach(MIMEText(body, 'html'))

    # Add attachments
    if attachments:
        for attachment in attachments:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment['data'])
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{attachment["filename"]}"'
            )
            message.attach(part)

    # Send
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(
        userId='me',
        body={'raw': raw}
    ).execute()
```

### 7.2 OCR Integration (Mistral AI)

#### 7.2.1 Mistral OCR API Call

```python
from mistralai import Mistral

class MistralOCRProvider(BaseOCRProvider):
    def extract_text(self, image_data: bytes) -> str:
        client = Mistral(api_key=self.api_key)

        # Upload image
        uploaded_file = client.files.upload(
            file={
                "file_name": "business_card.jpg",
                "content": image_data,
                "mime_type": "image/jpeg"
            }
        )

        # Get signed URL
        signed_url = client.files.get_signed_url(file_id=uploaded_file.id).url

        # Run OCR
        ocr_response = client.ocr.parse(
            model=self.model,
            document={
                "type": "document_url",
                "document_url": signed_url
            }
        )

        # Extract text from response
        return ocr_response.pages[0].markdown
```

#### 7.2.2 OCR Response Processing

```python
# Raw OCR output (markdown format):
# **John Doe**
# CEO
# **Example Corporation**
# john@example.com
# +1-555-1234
# www.example.com

# Processed to vCard format:
{
    "fn": ["John Doe"],
    "title": "CEO",
    "org": "Example Corporation",
    "email": ["john@example.com"],
    "tel": ["+1-555-1234"],
    "url": ["www.example.com"]
}
```

### 7.3 AI/LLM Integration (Groq & Gemini)

#### 7.3.1 Text Structuring with LLM

**Prompt:**
```
Extract and structure business card information into vCard JSON format.

Extracted Text:
{raw_ocr_text}

Return ONLY valid JSON in this format:
{
  "fn": ["Full Name"],
  "org": "Company Name",
  "title": "Job Title",
  "tel": ["phone1", "phone2"],
  "email": ["email1", "email2"],
  "url": ["website1", "website2"],
  "adr": ["Address"],
  "cat": ["Business Category"],
  "notes": "Additional context"
}

Rules:
- Extract all phone numbers found
- Extract all email addresses found
- Infer business category from company name/keywords
- Combine multiple addresses into array
- If field not found, omit from JSON
```

**API Call (LiteLLM):**
```python
from litellm import completion

response = completion(
    model="groq/llama-3.1-8b-instant",  # or "gemini/gemini-flash-lite-latest"
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"}
)

structured_data = json.loads(response.choices[0].message.content)
```

#### 7.3.2 Model Selection

| Use Case | Recommended Model | Speed | Cost | Accuracy |
|----------|------------------|-------|------|----------|
| Contact Structuring | Groq Llama 3.1-8b | ~100ms | Low | 90%+ |
| Complex Cards | Groq Llama 3.3-70b | ~300ms | Medium | 95%+ |
| Multilingual | Gemini Flash | ~200ms | Medium | 92%+ |

### 7.4 SMTP Email Integration

**Configuration:**
```python
SMTP_HOST = "smtp.hostinger.com"
SMTP_PORT = 465
SMTP_USER = "support@card2contacts.com"
SMTP_PASSWORD = "encrypted_password"
SMTP_FROM = "Card2Contacts <support@card2contacts.com>"
```

**Email Types:**
1. **OTP Verification** - 6-digit code for login
2. **Welcome Email** - New user registration
3. **Credential Email** - Distributor-created accounts
4. **Password Reset** - Password reset confirmation
5. **License Expiration** - 30/7/1 day warnings

---

## 8. Business Logic Flows

### 8.1 Free Tier to Licensed Conversion Flow

```
User Registration (Free)
    ↓
Grants 4 free scans
    ↓
User scans 4 cards
    ↓
scan_count = 4
    ↓
5th scan attempt
    ↓
Check: scan_count >= FREE_TIER_SCAN_LIMIT (4)
    ↓
Block scan, show upgrade message
    ↓
User contacts distributor
    ↓
Distributor creates licensed account
    ↓
Link new license to user (user.license_id)
    ↓
Reset scan_count = 0
    ↓
User logs in with new credentials
    ↓
Unlimited scans enabled
```

### 8.2 Bulk Scanning Flow

```
User enables bulk mode (toggle in UI)
    ↓
Upload multiple images (up to 100)
    ↓
POST /api/scan/bulk/stage
    ↓
Upload images to Google Drive: DigiCard/Bulk Staging/
    ↓
Track in Not_Submitted_Bulk sheet:
    - image_id
    - image_url
    - staged_at
    ↓
Repeat until all images staged
    ↓
User clicks "Submit All"
    ↓
POST /api/scan/bulk/submit
    ↓
Trigger background task
    ↓
For each staged image:
    1. Download from Drive
    2. Call OCR API
    3. Call LLM API
    4. Save to Google Sheets
    5. Send auto-email (if enabled)
    6. Update status in Bulk_Submitted sheet
    ↓
All complete → Notify user
```

### 8.3 Sub-Account Scanning Flow

```
Sub-account logs in (with username/password)
    ↓
OTP sent to enterprise admin's email
    ↓
Sub-account enters OTP
    ↓
Authentication successful
    ↓
Sub-account scans business card
    ↓
POST /api/scan/ocr (same endpoint as single user)
    ↓
Use enterprise admin's Google credentials
    ↓
OCR + LLM processing
    ↓
POST /api/scan/save
    ↓
Save to dedicated sheet: SubAccount_{username}
    ↓
If assigned_template_id exists:
    Send email via admin's Gmail account
    Using template from Email_Templates sheet
    ↓
Success
```

### 8.4 Distributor Account Creation Flow

```
Distributor logs in
    ↓
Access account creation dashboard
    ↓
Select account type: Single or Enterprise
    ↓
Enter customer email
    ↓
POST /api/distributor/create-account
    ↓
Generate license key
    ↓
Create License record
    ↓
Create User or EnterpriseAdmin record
    ↓
Set created_by_distributor_id
    ↓
Generate random temporary password
    ↓
Set requires_password_change = True
    ↓
Create DistributorLicense record
    ↓
Send credentials email to customer
    ↓
Return success to distributor
```

### 8.5 License Expiration Handling

```
Cron job runs daily
    ↓
Query: License WHERE is_active = true
    ↓
For each license:
    Check: created_at < NOW() - 1 year
    ↓
If expired:
    Check: created_at < NOW() - 1 year + 30 days
    ↓
If 30 days before expiration:
    Send warning email
    ↓
If fully expired:
    Set license.is_active = false
    ↓
Send expiration email
    ↓
User login blocked until renewal
```

---

## 9. Frontend Architecture

### 9.1 Application Structure

```
frontend/
├── index.html          # Main SPA for users
├── admin.html          # Admin dashboard
├── app.js              # Main application logic
├── admin.js            # Admin dashboard logic
├── config.js           # Frontend configuration
└── style.css           # Styling
```

### 9.2 State Management

**Global State Object:**
```javascript
const state = {
    userEmail: null,
    token: localStorage.getItem('access_token'),
    userType: 'single',
    isDistributor: false,
    licenseStatus: 'none',
    scansRemaining: null,
    mode: 'single',
    isBulk: false,
    isLoginView: true,
    isGoogleLinked: false,
    isGoogleConnected: false,
    selectedTemplate: null
};
```

### 9.3 Key Components

#### 9.3.1 Camera Component

```javascript
async function startCamera() {
    const constraints = {
        video: {
            facingMode: state.mode === 'dual' ? 'environment' : 'user',
            width: { ideal: 1920 },
            height: { ideal: 1080 }
        }
    };

    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    videoElement.srcObject = stream;
}

function captureImage() {
    const canvas = document.createElement('canvas');
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;
    canvas.getContext('2d').drawImage(videoElement, 0, 0);

    // Flash animation
    triggerFlashEffect();

    return canvas.toBlob((blob) => {
        // Send to backend
        uploadToBackend(blob);
    }, 'image/jpeg', 0.95);
}
```

#### 9.3.2 Google OAuth Handler

```javascript
async function handleGoogleLogin() {
    window.location.href = `${CONFIG.API_BASE_URL}/api/auth/google`;
}

// On callback
function handleGoogleCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    const error = urlParams.get('error');

    if (token) {
        localStorage.setItem('access_token', token);
        state.token = token;
        checkGoogleConnection();
    } else if (error) {
        showError(error);
    }
}
```

#### 9.3.3 Contact Review Modal

```javascript
function showContactReview(contactData) {
    showModal('Review Contact', `
        <div class="contact-review-form">
            <label>Contact Name:</label>
            <input type="text" id="fn" value="${contactData.fn || ''}">

            <label>Company:</label>
            <input type="text" id="org" value="${contactData.org || ''}">

            <!-- More fields... -->

            <button onclick="saveContact()">Save Contact</button>
            <button onclick="cancelScan()">Cancel</button>
        </div>
    `);
}
```

### 9.4 API Client Wrapper

```javascript
async function apiCall(endpoint, method = 'GET', data = null, isFormData = false) {
    const headers = {};

    if (!isFormData) {
        headers['Content-Type'] = 'application/json';
    }

    if (state.token) {
        headers['Authorization'] = `Bearer ${state.token}`;
    }

    const config = {
        method,
        headers,
        credentials: 'include'
    };

    if (data) {
        if (isFormData) {
            config.body = data;
        } else {
            config.body = JSON.stringify(data);
        }
    }

    const response = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`, config);

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'API Error');
    }

    return response.json();
}
```

### 9.5 UI States & Views

| View | Description | Access Control |
|------|-------------|----------------|
| Login | Email/password + OTP input | All users |
| Dashboard | Scan status, stats, actions | All authenticated users |
| Camera | Live camera view, capture button | All authenticated users |
| Contact Review | Edit extracted data before save | All authenticated users |
| Templates | Email template management | Single users, Enterprise admins |
| Sub-Accounts | Team management | Enterprise admins only |
| Admin Dashboard | Platform statistics | App owners only |

### 9.6 Progressive Web App Features

**Manifest (embedded):**
```html
<link rel="manifest" href='data:application/manifest+json,{
    "name": "DigiCard",
    "short_name": "DigiCard",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#ffffff",
    "theme_color": "#007bff",
    "orientation": "portrait"
}'>
```

**Installability Criteria:**
- PWA manifest ✓
- HTTPS ✓
- Service worker (optional for this implementation) ✓

---

## 10. Configuration Management

### 10.1 Backend Configuration (`backend/config.py`)

All configuration centralized in `Settings` class using pydantic-settings:

```python
class Settings(BaseSettings):
    # Deployment
    ENVIRONMENT: str = "development"
    FRONTEND_URL: str = "https://yourdomain.com"
    BACKEND_URL: str = "https://yourdomain.com"
    ALLOWED_ORIGINS: str = "*"

    # Database
    DATABASE_URL: str = "postgresql://user:pass@host:5432/db"

    # Authentication
    SECRET_KEY: str = "random-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days

    # Google OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    REDIRECT_URI: str = "https://yourdomain.com/api/auth/google/callback"

    # AI/LLM
    LLM_MODEL: str = "llama-3.1-8b-instant"
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # OCR
    OCR_PROVIDER: str = "mistral"
    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_MODEL: str = "mistral-ocr-2512"

    # Business Logic
    FREE_TIER_SCAN_LIMIT: int = 4
    DEFAULT_MAX_SUB_ACCOUNTS: int = 5

    class Config:
        env_file = ".env"
```

### 10.2 Frontend Configuration (`frontend/config.js`)

```javascript
const CONFIG = {
    ENVIRONMENT: 'production',
    API_BASE_URL: '',  // Same origin
    FRONTEND_URL: 'https://yourdomain.com',

    // Feature Flags
    ENABLE_BULK_SCANNING: true,
    ENABLE_EMAIL_TEMPLATES: true,
    ENABLE_DUAL_CAMERA: true,

    // UI Settings
    MAX_ATTACHMENT_SIZE: 20 * 1024 * 1024,  // 20MB
    ALLOWED_ATTACHMENT_TYPES: ['pdf', 'doc', 'docx', 'jpg', 'png'],

    // Logging
    ENABLE_CONSOLE_LOGS: false,
    ENABLE_ERROR_REPORTING: true
};
```

### 10.3 Environment Variables (`.env`)

```bash
# Deployment
ENVIRONMENT=production
FRONTEND_URL=https://yourdomain.com
BACKEND_URL=https://yourdomain.com
ALLOWED_ORIGINS=https://yourdomain.com

# Database
DATABASE_URL=postgresql://user:pass@host:5432/db

# Security
SECRET_KEY=your-secret-key-here

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
REDIRECT_URI=https://yourdomain.com/api/auth/google/callback

# AI/LLM
LLM_MODEL=groq/llama-3.1-8b-instant
GROQ_API_KEY=your-groq-key
GEMINI_API_KEY=your-gemini-key

# OCR
OCR_PROVIDER=mistral
MISTRAL_API_KEY=your-mistral-key
MISTRAL_MODEL=mistral-ocr-2512

# Business Logic
FREE_TIER_SCAN_LIMIT=4
DEFAULT_MAX_SUB_ACCOUNTS=5
```

### 10.4 Configuration Change Impact

| Configuration | Scope | Requires Restart |
|--------------|-------|------------------|
| Database URL | Backend | Yes |
| API Keys (Google, AI, OCR) | Backend | Yes |
| CORS Origins | Backend | Yes |
| Frontend URLs | Backend + Frontend | Yes |
| Business Logic (FREE_TIER_SCAN_LIMIT) | Backend | Yes |
| Frontend Feature Flags | Frontend | No (reload page) |

---

## 11. Feature Implementation Guide

### 11.1 Feature 1: Business Card Scanning with OCR

**Purpose:** Convert physical business cards to digital contacts using AI-powered OCR.

**Implementation Steps:**

1. **Frontend - Camera Access:**
   - Use HTML5 MediaDevices API
   - Request camera permissions
   - Display live video feed
   - Capture image on user action

2. **Backend - OCR Processing:**
   - Receive image via `POST /api/scan/ocr`
   - Call Mistral OCR API with image
   - Extract raw text from response

3. **Backend - AI Structuring:**
   - Send raw text to LLM (Groq/Gemini)
   - Request structured vCard JSON output
   - Parse and validate response

4. **Frontend - Contact Review:**
   - Display extracted data in form
   - Allow user to edit fields
   - Confirm or discard

**Key Files:**
- `frontend/app.js` (camera capture, OCR API call)
- `backend/main.py` (`/api/scan/ocr` endpoint)
- `backend/ocr/` (OCR provider implementations)

**Dependencies:**
- Mistral AI SDK
- LiteLLM
- OpenCV/Pillow

### 11.2 Feature 2: Google Workspace Integration

**Purpose:** Auto-save contacts to Google Sheets and send emails via Gmail.

**Implementation Steps:**

1. **OAuth 2.0 Flow:**
   - Implement Google OAuth 2.0 authorization flow
   - Request required scopes (Drive, Sheets, Gmail)
   - Exchange authorization code for tokens
   - Store refresh token in database

2. **Google Sheets Setup:**
   - Create spreadsheet in user's Drive
   - Set up folder structure
   - Create header rows in sheets

3. **Contact Save Operation:**
   - Append contact data to appropriate sheet
   - For sub-accounts: save to dedicated sheet

4. **Email Sending:**
   - Use Gmail API to send emails
   - Support attachments from Drive
   - Handle sending errors gracefully

**Key Files:**
- `backend/google_utils.py` (Google API operations)
- `backend/main.py` (OAuth endpoints, save logic)

**Dependencies:**
- Google Auth Libraries
- Google API Client Libraries

### 11.3 Feature 3: Email Automation

**Purpose:** Automatically send follow-up emails to new contacts.

**Implementation Steps:**

1. **Template Management:**
   - Create Email_Templates sheet in Google Sheets
   - Store subject, body (HTML), attachments
   - Allow create/edit/delete templates

2. **Template Assignment:**
   - Enterprise admins assign templates to sub-accounts
   - Track assignment in database

3. **Auto-Email Trigger:**
   - On contact save, check if auto-email enabled
   - Retrieve assigned template
   - Populate template with contact data (placeholders: {name}, {email}, etc.)
   - Send via Gmail API

**Key Files:**
- `backend/google_utils.py` (template operations)
- `backend/main.py` (email sending logic)

**Template Placeholders:**
- `{name}` - Contact's full name
- `{email}` - Contact's email
- `{company}` - Contact's company
- `{title}` - Contact's job title

### 11.4 Feature 4: User Authentication with OTP

**Purpose:** Secure login with email-based OTP verification.

**Implementation Steps:**

1. **Login Initiation:**
   - Receive email/username and password
   - Validate credentials
   - Generate 6-digit OTP
   - Send OTP via SMTP
   - Store OTP in database with expiration

2. **OTP Verification:**
   - Receive OTP and session token
   - Verify OTP code, expiration, attempts
   - Generate JWT token
   - Update session ID for single-device enforcement

3. **Session Management:**
   - Include session ID in JWT
   - Verify session ID on each request
   - Invalidate previous sessions on new login

**Key Files:**
- `backend/main.py` (auth endpoints)
- `backend/email_utils.py` (OTP email sending)
- `backend/database.py` (OTPRecord model)

**Security Features:**
- 5-minute OTP expiration
- Max 5 attempts
- Single-device enforcement
- Password hashing with bcrypt

### 11.5 Feature 5: Enterprise Team Management

**Purpose:** Multi-user accounts with centralized management.

**Implementation Steps:**

1. **Sub-Account Creation:**
   - Enterprise admin creates sub-accounts
   - Check seat limit from license
   - Generate credentials
   - Create dedicated sheet in admin's spreadsheet

2. **Sub-Account Permissions:**
   - Use admin's Google credentials
   - Cannot create templates (use assigned)
   - Cannot export (admin exports)
   - Limited to their own contacts

3. **Admin Controls:**
   - Activate/deactivate sub-accounts
   - Reset passwords
   - Assign email templates
   - Export combined contacts

**Key Files:**
- `backend/main.py` (sub-account endpoints)
- `backend/google_utils.py` (sheet creation, exports)

**Business Rules:**
- Sub-account OTP sent to admin's email
- Deactivation blocks login immediately
- Seat limit enforced at creation

### 11.6 Feature 6: Bulk Scanning Mode

**Purpose:** Process multiple business cards in batch for efficiency.

**Implementation Steps:**

1. **Image Staging:**
   - Upload multiple images to Google Drive staging folder
   - Track staged images in internal sheet

2. **Batch Submission:**
   - Trigger background processing task
   - Process images sequentially

3. **Background Processing:**
   - For each image: OCR → LLM → Save → Email
   - Update status in tracking sheet
   - Handle errors gracefully

**Key Files:**
- `backend/main.py` (bulk endpoints)
- `backend/google_utils.py` (staging, processing)

**Limits:**
- Max 100 images per batch
- Estimated 5-10 minutes for full batch

### 11.7 Feature 7: Distributor Program

**Purpose:** Enable resellers to create and manage customer accounts.

**Implementation Steps:**

1. **Distributor Role:**
   - Assign distributor role to any user type
   - Track in Distributor table
   - Activate/deactivate distributors

2. **Account Creation:**
   - Distributor creates customer accounts
   - Generate license key
   - Create user record with distributor link
   - Send credentials via email

3. **Analytics:**
   - Track accounts created per distributor
   - Track account types
   - Track creation timeline

**Key Files:**
- `backend/main.py` (distributor endpoints)
- `backend/database.py` (Distributor models)

**Business Rules:**
- All accounts permanently linked to distributor
- Instant account creation (no pre-allocation)
- Used for commission tracking

### 11.8 Feature 8: Admin Dashboard

**Purpose:** Platform-wide monitoring and analytics.

**Implementation Steps:**

1. **Authentication:**
   - Separate AppOwner table
   - JWT-based auth
   - Full platform access

2. **Statistics Aggregation:**
   - Total users by type
   - Licensed vs unlicensed
   - Distributor activity
   - Recent account creation

3. **Distributor Analytics:**
   - Accounts created per distributor
   - Account type breakdown
   - Creation timeline

**Key Files:**
- `backend/main.py` (admin endpoints)
- `frontend/admin.js` (dashboard UI)

**Setup:**
- Run `python backend/create_app_owner.py` to create first admin

---

## 12. Deployment Architecture

### 12.1 Docker Compose Configuration

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    container_name: scanner_db
    restart: always
    environment:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: securepassword
      POSTGRES_DB: scanner_prod
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### 12.2 Server Requirements

**Minimum Requirements:**
- CPU: 2 cores
- RAM: 4GB
- Storage: 20GB SSD
- OS: Linux (Ubuntu 20.04+) or Windows Server

**Recommended for Production:**
- CPU: 4+ cores
- RAM: 8GB+
- Storage: 50GB+ SSD
- OS: Linux (Ubuntu 22.04 LTS)

### 12.3 Deployment Steps

1. **Prerequisites:**
   - Install Docker & Docker Compose
   - Obtain Google OAuth credentials
   - Obtain AI API keys (Groq, Mistral)
   - Configure SMTP server

2. **Environment Setup:**
   ```bash
   # Copy example env file
   cp .env.example .env

   # Edit .env with production values
   nano .env
   ```

3. **Database Setup:**
   ```bash
   # Start PostgreSQL
   docker-compose up -d db

   # Create app owner account
   python backend/create_app_owner.py
   ```

4. **Backend Deployment:**
   ```bash
   # Install dependencies
   pip install -r requirements.txt

   # Start backend
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```

5. **Frontend Deployment:**
   - Serve `frontend/` directory via web server (nginx, Apache)
   - Configure reverse proxy for API calls

6. **SSL/TLS:**
   - Configure HTTPS (required for Google OAuth)
   - Use Let's Encrypt or commercial certificate

### 12.4 Production Checklist

- [ ] HTTPS enabled (SSL certificate)
- [ ] Firewall configured (ports 443, 80 only)
- [ ] Google OAuth redirect URIs updated
- [ ] Strong SECRET_KEY set
- [ ] CORS origins restricted
- [ ] Database backed up
- [ ] Monitoring configured
- [ ] Error logging enabled
- [ ] Rate limiting configured
- [ ] SMTP credentials secured

### 12.5 Scaling Considerations

**Vertical Scaling:**
- Increase CPU/RAM on single server
- Suitable for up to 1000 concurrent users

**Horizontal Scaling:**
- Deploy multiple backend instances behind load balancer
- Use managed PostgreSQL (AWS RDS, Google Cloud SQL)
- Use managed object storage for images (S3, Cloud Storage)
- Suitable for 10,000+ concurrent users

---

## 13. Security Considerations

### 13.1 Authentication & Authorization

| Threat | Mitigation |
|--------|------------|
| Password exposure | Bcrypt hashing with salt |
| Session hijacking | Single-device enforcement via session ID |
| Token theft | Short token expiration (30 days), HTTPS only |
| Brute force | OTP max 5 attempts, rate limiting |

### 13.2 Data Protection

| Data Type | Protection |
|-----------|------------|
| User passwords | Bcrypt hashing |
| Google tokens | Encrypt at rest (implementation detail) |
| SMTP credentials | Environment variables |
| Database | TLS in transit, PostgreSQL encryption at rest |

### 13.3 API Security

- **CORS:** Restrict origins in production
- **Input Validation:** Pydantic models for all inputs
- **SQL Injection:** SQLModel/SQLAlchemy ORM (parameterized queries)
- **XSS:** Input sanitization, Content Security Policy

### 13.4 Google OAuth Security

- **Redirect URI validation:** Exact match in Google Console
- **Scope verification:** Check all required scopes granted
- **Token refresh:** Automatic refresh with error handling

### 13.5 Email Security

- **OTP in email:** Temporary (5 min), single-use
- **Password reset:** One-time use, force change on next login
- **SMTP:** TLS encryption (port 465 SSL)

---

## 14. Appendix

### 14.1 Database Schema Migration SQL

```sql
-- Create all tables
CREATE TABLE user (...);
CREATE TABLE enterpriseadmin (...);
CREATE TABLE subaccount (...);
CREATE TABLE license (...);
CREATE TABLE distributor (...);
CREATE TABLE distributorlicense (...);
CREATE TABLE distributorpurchase (...);
CREATE TABLE appowner (...);
CREATE TABLE otprecord (...);

-- Create indexes
CREATE INDEX idx_user_email ON user(email);
CREATE INDEX idx_enterprise_email ON enterpriseadmin(email);
CREATE INDEX idx_subaccount_email ON subaccount(email);
CREATE INDEX idx_license_key ON license(license_key);
CREATE INDEX idx_otp_identifier ON otprecord(identifier);
```

### 14.2 API Rate Limiting

**Recommended Limits:**
- Login attempts: 5 per minute per IP
- OTP verification: 5 per session
- Scan requests: 60 per minute per user
- Bulk submit: 10 per hour per user

### 14.3 Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (invalid/missing token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 429 | Too Many Requests (rate limit) |
| 500 | Internal Server Error |

### 14.4 Logging

**Backend Logs:**
- Application startup
- API requests/responses
- OAuth flow
- OCR/AI API calls
- Errors and exceptions

**Log Locations:**
- Development: Console output
- Production: File-based or cloud logging (CloudWatch, GCP Logging)

### 14.5 Monitoring Metrics

**Key Metrics:**
- User registrations per day
- Scans processed per day
- OCR success rate
- LLM API latency
- Google API errors
- Database query performance
- Response times (p50, p95, p99)

### 14.6 Backup Strategy

**Database Backups:**
- Daily automated backups
- Retain 30 days
- Off-site storage

**Google Data:**
- Stored in user's own Google Drive
- Consider export to local storage periodically

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-11 | Generated from codebase | Initial architecture document |

---

**End of Technical Architecture Document**
