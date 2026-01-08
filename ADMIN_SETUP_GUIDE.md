# App Owner/Developer Dashboard - Setup & Usage Guide

## Table of Contents
1. [Overview](#overview)
2. [Initial Setup](#initial-setup)
3. [Creating Your First App Owner Account](#creating-your-first-app-owner-account)
4. [Accessing the Dashboard](#accessing-the-dashboard)
5. [Dashboard Features](#dashboard-features)
6. [API Endpoints Reference](#api-endpoints-reference)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The App Owner Dashboard is a comprehensive monitoring tool for DigiCard app owners and developers. It provides:

- **Real-time system statistics** (users, licenses, distributors)
- **Distributor activity tracking** (who created which accounts and when)
- **Account creation timeline** (when accounts were created by each distributor)
- **Secure authentication** (JWT-based, session-controlled access)

---

## Initial Setup

### Prerequisites

Before you can access the admin dashboard, you need:

1. **Running DigiCard backend** (FastAPI server)
2. **Database configured** (PostgreSQL)
3. **Python environment** with all dependencies installed

### Database Migration

The `AppOwner` model has been added to the database schema. You need to ensure your database tables are up to date:

```bash
# The tables will be created automatically when you start the server
# Or run the create_app_owner script which calls create_db_and_tables()
```

---

## Creating Your First App Owner Account

### Step 1: Run the Setup Script

From your project root directory, run:

```bash
python backend/create_app_owner.py
```

### Step 2: Follow the Interactive Prompts

The script will ask you for:

1. **Email address** - This will be your login username
   - Must be a valid email format
   - Must be unique (not already registered)

2. **Full name** - Your display name in the dashboard
   - Example: "John Doe" or "Admin User"

3. **Password** - Your login password
   - Minimum 8 characters
   - You'll be asked to confirm it

### Step 3: Complete Setup

Once successful, you'll see:

```
==============================================================
✅ App Owner Account Created Successfully!
==============================================================

Email:     admin@example.com
Name:      John Doe
ID:        1
Created:   2024-01-15 10:30:45 UTC

==============================================================

You can now login to the admin dashboard at:
  http://localhost:8000/admin.html

Use the email and password you just created to login.
==============================================================
```

---

## Accessing the Dashboard

### Step 1: Start the Server

Make sure your FastAPI server is running:

```bash
# From your project root
uvicorn backend.main:app --reload --port 8000
```

### Step 2: Open the Dashboard

Navigate to:
```
http://localhost:8000/admin.html
```

### Step 3: Login

Enter your credentials:
- **Email**: The email you used during setup
- **Password**: The password you created

### Step 4: Explore the Dashboard

Once logged in, you'll see:
- **System statistics** at the top
- **Distributor activity** section below
- **Refresh button** to reload data
- **Logout button** in the header

---

## Dashboard Features

### 1. System Statistics Cards

The dashboard shows four key metrics:

#### Total Users
- **What it shows**: Total count of all users across all types
- **Includes**: Single users + Enterprise admins + Sub-accounts
- **Example**: 1,247 users

#### Licensed Users
- **What it shows**: Number of single users with active licenses
- **Excludes**: Unlicensed/trial users
- **Example**: 892 licensed users

#### Distributors
- **What it shows**: Number of active distributors
- **Only counts**: Distributors with `is_active = True`
- **Example**: 15 distributors

#### New Accounts (30d)
- **What it shows**: Accounts created in the last 30 days
- **Includes**: Both single and enterprise accounts
- **Example**: 134 new accounts

### 2. Distributor Activity Section

This is the main feature showing detailed distributor tracking.

#### For Each Distributor, You Can See:

**Header Information:**
- Distributor email address
- Distributor ID (database identifier)
- Account type (single, enterprise_admin, sub_account)
- Creation date (when they became a distributor)

**Statistics:**
- **Total**: Total accounts created by this distributor
- **Single**: Number of single login accounts created
- **Enterprise**: Number of enterprise accounts created

**Account List:**
- Click "View X Accounts" to expand/collapse
- Shows table with:
  - Email address of created account
  - Account type (Single or Enterprise)
  - Creation timestamp

#### Sorting:
- Distributors are sorted by total accounts created (descending)
- Most active distributors appear at the top

### 3. Refresh Functionality

- Click the **Refresh** button to reload all data
- Updates both system stats and distributor activity
- Useful for monitoring in real-time

### 4. Security Features

**Session Management:**
- JWT token-based authentication
- Single-device enforcement (logging in elsewhere invalidates previous session)
- Automatic logout on token expiration

**Access Control:**
- All admin endpoints require valid app owner authentication
- 401 errors automatically redirect to login

---

## API Endpoints Reference

All admin endpoints require authentication via JWT token in the query parameter.

### Authentication Endpoint

#### POST /api/admin/login
```json
Request:
{
    "email": "admin@example.com",
    "password": "your-password"
}

Response:
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "token_type": "bearer",
    "user_type": "app_owner",
    "full_name": "John Doe"
}
```

### Data Endpoints

#### GET /api/admin/profile?token=YOUR_TOKEN

Returns current app owner profile.

```json
Response:
{
    "email": "admin@example.com",
    "full_name": "John Doe",
    "created_at": "2024-01-15T10:30:45.123Z",
    "last_login": "2024-01-16T09:15:30.456Z"
}
```

#### GET /api/admin/system-stats?token=YOUR_TOKEN

Returns overall system statistics.

```json
Response:
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

#### GET /api/admin/distributor-activity?token=YOUR_TOKEN&distributor_id=OPTIONAL

Returns comprehensive distributor activity report.

**Query Parameters:**
- `token` (required): JWT authentication token
- `distributor_id` (optional): Filter by specific distributor ID

```json
Response:
{
    "total_distributors": 15,
    "distributors": [
        {
            "distributor_id": 1,
            "distributor_email": "distributor@example.com",
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
                },
                // ... more accounts
            ]
        },
        // ... more distributors
    ]
}
```

---

## Troubleshooting

### Problem: Can't Access Admin Dashboard

**Solution 1: Check if server is running**
```bash
# Should see server running on port 8000
curl http://localhost:8000/
```

**Solution 2: Verify admin.html exists**
```bash
# Check if file exists
ls frontend/admin.html
```

**Solution 3: Clear browser cache and cookies**
- Sometimes old sessions can cause issues
- Try accessing in incognito/private mode

### Problem: Login Fails with "Invalid credentials"

**Possible causes:**
1. Wrong email or password
2. Account doesn't exist
3. Account is deactivated

**Solutions:**
- Verify your email and password
- Run `python backend/create_app_owner.py` to create a new account
- Check database: `SELECT * FROM appowner WHERE email = 'your@email.com';`

### Problem: Session Expired Error

**Cause:** JWT token expired or invalid

**Solution:**
- Logout and login again
- Token is valid for the duration set in `ACCESS_TOKEN_EXPIRE_MINUTES`
- Check `backend/config.py` for token expiration settings

### Problem: Empty Dashboard / No Data

**Possible causes:**
1. No distributors created yet
2. No accounts created by distributors
3. Database connection issues

**Solutions:**
- Verify distributors exist: `SELECT * FROM distributor WHERE is_active = true;`
- Check if distributor tracking fields are populated in User/EnterpriseAdmin tables
- Ensure `created_by_distributor_id` field exists in tables

### Problem: "Failed to load distributor activity"

**Cause:** API endpoint error

**Solutions:**
1. Check browser console for detailed error
2. Check server logs for backend errors
3. Verify token is valid: Check `/api/admin/profile` endpoint
4. Ensure database migrations ran successfully

### Database Schema Verification

To verify the AppOwner table exists:

```sql
-- Connect to your PostgreSQL database
psql -U admin -d scanner_prod

-- Check if AppOwner table exists
\dt appowner

-- View table structure
\d appowner

-- Check if created_by_distributor_id field exists in User table
\d user

-- View sample data
SELECT * FROM appowner LIMIT 5;
```

---

## Security Best Practices

### 1. Strong Passwords
- Use passwords with at least 12 characters
- Include uppercase, lowercase, numbers, and symbols
- Don't reuse passwords from other systems

### 2. Limited Access
- Only create app owner accounts for trusted developers
- Regularly review who has access
- Deactivate accounts that are no longer needed

### 3. Production Considerations
- Use HTTPS in production (not HTTP)
- Set strong `SECRET_KEY` in environment variables
- Consider adding IP whitelisting for admin endpoints
- Enable rate limiting on authentication endpoints

### 4. Monitoring
- Regularly check the `last_login` field for unusual activity
- Monitor for failed login attempts
- Keep audit logs of admin actions

---

## Next Steps

Now that you have the admin dashboard set up:

1. **Create distributor accounts** using your main application
2. **Assign distributor roles** to trusted users
3. **Monitor activity** through the admin dashboard
4. **Track which distributors** are most active
5. **Analyze account creation** patterns and trends

For additional features or customization, you can:
- Modify the dashboard UI in `frontend/admin.html`
- Extend the API with new endpoints in `backend/main.py`
- Add more analytics and reporting features
- Create export functionality for reports

---

## Support

If you encounter issues not covered in this guide:

1. Check server logs for error details
2. Review browser console for frontend errors
3. Verify database schema is up to date
4. Test API endpoints directly using curl or Postman

For feature requests or bug reports, document the issue with:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Error messages (if any)
- Screenshots (if applicable)

---

**Last Updated:** 2024-01-16
**Version:** 1.0.0
