import os
import io
import json
import base64
from typing import Optional, List, Callable, Dict, Any
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from fastapi import HTTPException
from sqlmodel import Session

from backend.database import User, EnterpriseAdmin, SubAccount, safe_commit

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.modify",
]

INTERNAL_FOLDER_NAME = ".Digital_Business_Card_Scanner_Internal_Data"
BULK_IMAGES_FOLDER = "Card2Contacts_Bulk_Temp_Images"
TEMPLATE_ATTACHMENTS_FOLDER = "Email_Template_Attachments"
SHEET_FILENAME = "Card2Contacts_Contacts"
TEMPLATE_SHEET_NAME = "Email_Templates"
STAGING_SHEET_NAME = "Not_Submitted_Bulk"
QUEUE_SHEET_NAME = "Bulk_Submitted"

# HEADERS CONFIG
# Current Version (10 Cols)
HEADERS_V2 = [
    "Contact Name",
    "Business Name",
    "Contact Numbers",
    "Job Title",
    "Emails",
    "Websites",
    "Address",
    "Import Source",
    "Business Category",
    "AI Notes",
]


def force_text(value):
    """
    Convert any value to a string that Google Sheets treats as text.

    By prepending a single quote (') to values, we force Google Sheets
    to interpret them as text instead of formulas. This prevents values
    starting with '+', '=', '-' (like phone numbers "+1") from
    being treated as formulas.

    Args:
        value: Any value (string, list, None, etc.)

    Returns:
        String with leading quote for text interpretation
    """
    if value is None:
        return ""
    return f"'{str(value)}"


# ==========================================
# ERROR HANDLING (USER FRIENDLY)
# ==========================================


def handle_google_api_error(e: HttpError, context: str = "operation"):
    try:
        error_details = json.loads(e.content.decode())
        error_msg = error_details.get("error", {}).get("message", str(e))
        error_reason = (
            error_details.get("error", {}).get("errors", [{}])[0].get("reason", "")
        )
    except:
        error_msg = str(e)
        error_reason = ""

    print(f"⚠️ Google API Error ({context}): {e.resp.status} - {error_msg}")

    if e.resp.status == 401 or "invalid_grant" in error_msg:
        raise HTTPException(
            status_code=401,
            detail="Your Google session has expired. Please Re-link your account in the Dashboard.",
        )

    if e.resp.status == 403:
        if "insufficientPermissions" in error_msg or "insufficient_scope" in error_msg:
            raise HTTPException(
                status_code=403,
                detail="Card2Contacts lacks permission to access Drive or Sheets. Please Re-link and ensure all checkboxes are checked.",
            )
        if "usageLimits" in error_msg:
            raise HTTPException(
                status_code=429,
                detail="Google API usage limit exceeded. Please try again later.",
            )

        raise HTTPException(
            status_code=403,
            detail="Google Access Denied. You may have revoked permissions in your Google Account settings.",
        )

    if e.resp.status == 404:
        raise HTTPException(
            status_code=404,
            detail=f"The requested Google file or sheet was not found. It may have been deleted.",
        )

    if "storageQuotaExceeded" in error_reason:
        raise HTTPException(
            status_code=507, detail="Your Google Drive storage is full."
        )

    raise HTTPException(
        status_code=502, detail=f"Google Error during {context}: {error_msg}"
    )


# ==========================================
# AUTHENTICATION
# ==========================================


def get_google_creds(user, db: Session):
    """
    Overloaded function that works with User or EnterpriseAdmin.
    """
    if not user.google_refresh_token:
        return None

    creds = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_uri=user.google_token_uri,
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        scopes=SCOPES,
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            user.google_access_token = creds.token
            db.add(user)
            if not safe_commit(db):
                print(f"Token Refresh DB Commit Failed")
                return None
        except RefreshError:
            user_id = getattr(user, "email", None) or getattr(
                user, "username", "Unknown"
            )
            print(f"⚠️ Google Token Revoked for {user_id}. Disconnecting.")
            user.google_connected = False
            user.google_access_token = None
            user.google_refresh_token = None
            db.add(user)
            safe_commit(db)
            return None
        except Exception as e:
            print(f"Token Refresh Network Error: {e}")
            return None

    return creds


def ensure_creds(user, db: Session):
    """
    Overloaded function that works with User or EnterpriseAdmin.
    """
    creds = get_google_creds(user, db)
    if not creds:
        raise HTTPException(
            status_code=403, detail="Google connection broken. Please Re-link Account."
        )
    return creds


def verify_connection_health(user: User, db: Session):
    creds = ensure_creds(user, db)
    try:
        drive_service = build("drive", "v3", credentials=creds)
        drive_service.files().list(pageSize=1, fields="files(id)").execute()
        return True
    except HttpError as e:
        handle_google_api_error(e, "Connection Check")


def check_granted_scopes(user, db: Session):
    """
    Check which scopes are actually granted to the user.
    Returns a dict with:
    - has_all_scopes: bool
    - missing_scopes: list of missing scope names
    """
    creds = get_google_creds(user, db)
    if not creds:
        return {
            "has_all_scopes": False,
            "missing_scopes": ["Drive Access", "Gmail Access"],
        }

    # Get granted scopes from credentials
    granted_scopes = (
        set(creds.scopes) if hasattr(creds, "scopes") and creds.scopes else set()
    )

    # Check for required scopes
    required_scopes = {
        "https://www.googleapis.com/auth/drive": "Drive Access",
        "https://www.googleapis.com/auth/gmail.send": "Gmail Send",
    }

    # Alternative Gmail scope (either gmail.send or gmail.modify is acceptable)
    has_gmail = (
        "https://www.googleapis.com/auth/gmail.send" in granted_scopes
        or "https://www.googleapis.com/auth/gmail.modify" in granted_scopes
    )

    missing = []

    # Check Drive
    if "https://www.googleapis.com/auth/drive" not in granted_scopes:
        missing.append("Drive Access")

    # Check Gmail
    if not has_gmail:
        missing.append("Gmail Access")

    return {"has_all_scopes": len(missing) == 0, "missing_scopes": missing}


# ==========================================
# DRIVE & FOLDER MANAGEMENT
# ==========================================


def get_or_create_folder(drive_service, folder_name, parent_id=None):
    try:
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        results = (
            drive_service.files()
            .list(q=query, spaces="drive", fields="files(id, name)")
            .execute()
        )
        files = results.get("files", [])

        if files:
            return files[0]["id"]

        metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]

        folder = drive_service.files().create(body=metadata, fields="id").execute()
        return folder.get("id")
    except HttpError as e:
        handle_google_api_error(e, "Folder Creation")


def get_app_folders(creds):
    try:
        service = build("drive", "v3", credentials=creds)
        main_id = get_or_create_folder(service, INTERNAL_FOLDER_NAME)
        bulk_id = get_or_create_folder(service, BULK_IMAGES_FOLDER, parent_id=main_id)
        return main_id, bulk_id
    except HttpError as e:
        handle_google_api_error(e, "Folder Setup")


def get_or_create_app_folder(drive_service):
    return get_or_create_folder(drive_service, INTERNAL_FOLDER_NAME)


# ==========================================
# TEMPLATE ATTACHMENT STORAGE (GOOGLE DRIVE)
# ==========================================


def upload_template_attachments_to_drive(
    drive_service, attachments: list[dict], app_folder_id: str
):
    """
    Upload template attachments to Google Drive to avoid 50k char/cell limit.

    Args:
        drive_service: Google Drive API service
        attachments: List of {filename: str, data: str (base64), size: int}
        app_folder_id: Parent folder ID for the app

    Returns:
        List of {filename: str, drive_file_id: str, size: int}
    """
    if not attachments:
        return []

    try:
        # Get or create the Template Attachments folder
        attachments_folder_id = get_or_create_folder(
            drive_service, TEMPLATE_ATTACHMENTS_FOLDER, parent_id=app_folder_id
        )

        uploaded_files = []
        for attachment in attachments:
            filename = attachment.get("filename", "attachment")
            base64_data = attachment.get("data", "")
            size = attachment.get("size", 0)

            if not base64_data:
                continue

            # Decode base64 to binary
            file_data = base64.b64decode(base64_data)

            # Create media upload
            media = MediaIoBaseUpload(
                io.BytesIO(file_data),
                mimetype="application/octet-stream",
                resumable=True,
            )

            # Upload to Drive
            file_metadata = {"name": filename, "parents": [attachments_folder_id]}

            file = (
                drive_service.files()
                .create(body=file_metadata, media_body=media, fields="id")
                .execute()
            )

            uploaded_files.append(
                {"filename": filename, "drive_file_id": file.get("id"), "size": size}
            )

        return uploaded_files
    except HttpError as e:
        handle_google_api_error(e, "Uploading Template Attachments")


def download_template_attachments_from_drive(
    drive_service, attachment_refs: list[dict]
):
    """
    Download template attachments from Google Drive.

    Args:
        drive_service: Google Drive API service
        attachment_refs: List of {filename: str, drive_file_id: str, size: int}

    Returns:
        List of {filename: str, data: str (base64), size: int}
    """
    if not attachment_refs:
        return []

    try:
        attachments = []
        for ref in attachment_refs:
            file_id = ref.get("drive_file_id")
            filename = ref.get("filename", "attachment")
            size = ref.get("size", 0)

            if not file_id:
                continue

            # Download file from Drive
            request = drive_service.files().get_media(fileId=file_id)
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()

            # Encode to base64
            file_buffer.seek(0)
            base64_data = base64.b64encode(file_buffer.read()).decode("utf-8")

            attachments.append(
                {"filename": filename, "data": base64_data, "size": size}
            )

        return attachments
    except HttpError as e:
        handle_google_api_error(e, "Downloading Template Attachments")


def get_template_attachments(user, db: Session, attachment_refs: list[dict]):
    """
    Helper function to get template attachments ready for email sending.
    Converts Drive file references to base64 data suitable for send_gmail().

    Args:
        user: User or EnterpriseAdmin object
        db: Database session
        attachment_refs: List from template (can be Drive refs or old base64 format)

    Returns:
        List of {filename: str, data: str (base64), size: int} or None
    """
    if not attachment_refs:
        return None

    # Check if this is the new format (Drive file IDs) or old format (base64 data)
    if attachment_refs and isinstance(attachment_refs[0], dict):
        if "drive_file_id" in attachment_refs[0]:
            # New format - download from Drive
            creds = ensure_creds(user, db)
            drive_service = build("drive", "v3", credentials=creds)
            return download_template_attachments_from_drive(
                drive_service, attachment_refs
            )
        elif "data" in attachment_refs[0]:
            # Old format - already has base64 data
            return attachment_refs

    return None


# ==========================================
# SPREADSHEET INFRASTRUCTURE
# ==========================================


def ensure_bulk_sheets(service, spreadsheet_id):
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        existing_titles = [s["properties"]["title"] for s in meta.get("sheets", [])]

        reqs = []
        if STAGING_SHEET_NAME not in existing_titles:
            reqs.append({"addSheet": {"properties": {"title": STAGING_SHEET_NAME}}})
        if QUEUE_SHEET_NAME not in existing_titles:
            reqs.append({"addSheet": {"properties": {"title": QUEUE_SHEET_NAME}}})

        if reqs:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body={"requests": reqs}
            ).execute()
    except HttpError as e:
        handle_google_api_error(e, "Ensuring Bulk Sheets")


def create_spreadsheet_in_folder(creds):
    try:
        service = build("sheets", "v4", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        folder_id = get_or_create_app_folder(drive_service)
        if not folder_id:
            return None

        file_metadata = {
            "name": SHEET_FILENAME,
            "parents": [folder_id],
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }

        file = drive_service.files().create(body=file_metadata, fields="id").execute()
        ssid = file.get("id")

        # Create with V2 Headers
        service.spreadsheets().values().update(
            spreadsheetId=ssid,
            range="A1",
            valueInputOption="RAW",
            body={"values": [HEADERS_V2]},
        ).execute()

        return ssid
    except HttpError as e:
        handle_google_api_error(e, "Spreadsheet Creation")
        return None


# ==========================================
# SCHEMA MIGRATION LOGIC
# ==========================================


def ensure_schema_v2(service, spreadsheet_id):
    """
    Checks if the sheet is missing the 'Business Category' column (Old V1 Schema).
    If missing, it inserts a column at Index 8 (Column I) and adds the header.
    This shifts existing 'AI Notes' from I to J, preserving data.
    """
    try:
        # 1. Fetch current headers (First row)
        res = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range="A1:Z1")
            .execute()
        )
        headers = res.get("values", [[]])[0]

        # Check for V2 Signature
        if "Business Category" in headers:
            return  # Already V2

        print("--- Migrating Sheet to V2 Schema (Adding Category Column) ---")

        # 2. Get Sheet ID (Integer) for the first sheet (Contacts)
        sheet_meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        # Assuming contacts are on the first sheet
        sheet_id = sheet_meta["sheets"][0]["properties"]["sheetId"]

        # 3. Batch Update: Insert Column & Update Header
        requests = [
            {
                "insertDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 8,  # Index 8 is Column I
                        "endIndex": 9,
                    },
                    "inheritFromBefore": True,
                }
            },
            {
                "updateCells": {
                    "rows": [
                        {
                            "values": [
                                {
                                    "userEnteredValue": {
                                        "stringValue": "Business Category"
                                    }
                                }
                            ]
                        }
                    ],
                    "fields": "userEnteredValue",
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 8,
                        "endColumnIndex": 9,
                    },
                }
            },
        ]

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()
        print("--- Migration Complete ---")

    except HttpError as e:
        print(f"Schema Migration Warning: {e}")
        # Don't raise hard error, try to proceed with append
    except Exception as e:
        print(f"Schema Migration Error: {e}")


# ==========================================
# BULK UPLOAD LOGIC
# ==========================================


def get_sub_account_bulk_sheet_names(sub_account: SubAccount):
    """Get the staging and queue sheet names for a sub-account."""
    if not sub_account.sheet_name:
        raise HTTPException(status_code=400, detail="Sub-account sheet not created")
    staging_sheet = f"{sub_account.sheet_name}_Not_Submitted"
    queue_sheet = f"{sub_account.sheet_name}_Bulk_Submitted"
    return staging_sheet, queue_sheet


def stage_bulk_image_sub_account(
    admin: EnterpriseAdmin,
    sub_account: SubAccount,
    db: Session,
    file_obj: bytes,
    filename: str,
):
    """
    Stage a bulk image for a sub-account.
    Uses admin's Google Drive but sub-account's staging sheet.
    """
    creds = ensure_creds(admin, db)
    try:
        drive_service = build("drive", "v3", credentials=creds)
        sheets_service = build("sheets", "v4", credentials=creds)

        _, bulk_folder_id = get_app_folders(creds)

        file_metadata = {"name": filename, "parents": [bulk_folder_id]}
        media = MediaIoBaseUpload(
            io.BytesIO(file_obj), mimetype="image/jpeg", resumable=True
        )

        file = (
            drive_service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )
        file_id = file.get("id")

        # Ensure sub-account's bulk sheets exist
        staging_sheet, queue_sheet = get_sub_account_bulk_sheet_names(sub_account)
        ensure_sub_account_bulk_sheets(
            sheets_service, admin.google_spreadsheet_id, staging_sheet, queue_sheet
        )

        row = [file_id, "Pending Upload"]
        sheets_service.spreadsheets().values().append(
            spreadsheetId=admin.google_spreadsheet_id,
            range=f"{staging_sheet}!A1",
            valueInputOption="RAW",
            body={"values": [row]},
        ).execute()

        return file_id
    except HttpError as e:
        handle_google_api_error(e, "Staging Image")


def ensure_sub_account_bulk_sheets(
    service, spreadsheet_id: str, staging_sheet: str, queue_sheet: str
):
    """Ensure sub-account's bulk processing sheets exist."""
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        existing_titles = [s["properties"]["title"] for s in meta.get("sheets", [])]

        reqs = []
        if staging_sheet not in existing_titles:
            reqs.append({"addSheet": {"properties": {"title": staging_sheet}}})
        if queue_sheet not in existing_titles:
            reqs.append({"addSheet": {"properties": {"title": queue_sheet}}})

        if reqs:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body={"requests": reqs}
            ).execute()
    except HttpError as e:
        handle_google_api_error(e, "Ensuring Sub-Account Bulk Sheets")


def check_staging_count_for_user(admin, user, user_type: str, db: Session):
    """
    Check staging count for any user type.
    For sub-accounts, checks their dedicated staging sheet.
    """
    creds = ensure_creds(admin, db)
    try:
        service = build("sheets", "v4", credentials=creds)

        if user_type == "sub_account":
            staging_sheet, _ = get_sub_account_bulk_sheet_names(user)
            ensure_sub_account_bulk_sheets(
                service, admin.google_spreadsheet_id, staging_sheet, _
            )
            sheet_range = f"{staging_sheet}!A:A"
        else:
            ensure_bulk_sheets(service, admin.google_spreadsheet_id)
            sheet_range = f"{STAGING_SHEET_NAME}!A:A"

        res = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=admin.google_spreadsheet_id, range=sheet_range)
            .execute()
        )
        values = res.get("values", [])
        return len(values)
    except HttpError as e:
        handle_google_api_error(e, "Checking Bulk Status")


def stage_bulk_image(user: User, db: Session, file_obj: bytes, filename: str):
    creds = ensure_creds(user, db)
    try:
        drive_service = build("drive", "v3", credentials=creds)
        sheets_service = build("sheets", "v4", credentials=creds)

        _, bulk_folder_id = get_app_folders(creds)

        file_metadata = {"name": filename, "parents": [bulk_folder_id]}
        media = MediaIoBaseUpload(
            io.BytesIO(file_obj), mimetype="image/jpeg", resumable=True
        )

        file = (
            drive_service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )
        file_id = file.get("id")

        ensure_bulk_sheets(sheets_service, user.google_spreadsheet_id)

        row = [file_id, "Pending Upload"]
        sheets_service.spreadsheets().values().append(
            spreadsheetId=user.google_spreadsheet_id,
            range=f"{STAGING_SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={"values": [row]},
        ).execute()

        return file_id
    except HttpError as e:
        handle_google_api_error(e, "Staging Image")


def check_staging_count(user: User, db: Session):
    creds = ensure_creds(user, db)
    try:
        service = build("sheets", "v4", credentials=creds)
        ensure_bulk_sheets(service, user.google_spreadsheet_id)

        res = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=user.google_spreadsheet_id,
                range=f"{STAGING_SHEET_NAME}!A:A",
            )
            .execute()
        )
        values = res.get("values", [])
        return len(values)
    except HttpError as e:
        handle_google_api_error(e, "Checking Bulk Status")


def submit_bulk_session(user: User, db: Session):
    creds = ensure_creds(user, db)
    try:
        service = build("sheets", "v4", credentials=creds)

        res = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=user.google_spreadsheet_id,
                range=f"{STAGING_SHEET_NAME}!A:B",
            )
            .execute()
        )
        rows = res.get("values", [])

        if not rows:
            return 0

        service.spreadsheets().values().append(
            spreadsheetId=user.google_spreadsheet_id,
            range=f"{QUEUE_SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        service.spreadsheets().values().clear(
            spreadsheetId=user.google_spreadsheet_id, range=f"{STAGING_SHEET_NAME}!A:B"
        ).execute()

        return len(rows)
    except HttpError as e:
        handle_google_api_error(e, "Submitting Batch")


def submit_bulk_session_sub_account(
    admin: EnterpriseAdmin, sub_account: SubAccount, db: Session
):
    """Move sub-account's staging data to queue."""
    creds = ensure_creds(admin, db)
    try:
        service = build("sheets", "v4", credentials=creds)
        staging_sheet, queue_sheet = get_sub_account_bulk_sheet_names(sub_account)

        res = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=admin.google_spreadsheet_id, range=f"{staging_sheet}!A:B"
            )
            .execute()
        )
        rows = res.get("values", [])

        if not rows:
            return 0

        service.spreadsheets().values().append(
            spreadsheetId=admin.google_spreadsheet_id,
            range=f"{queue_sheet}!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        service.spreadsheets().values().clear(
            spreadsheetId=admin.google_spreadsheet_id, range=f"{staging_sheet}!A:B"
        ).execute()

        return len(rows)
    except HttpError as e:
        handle_google_api_error(e, "Submitting Batch")


def clear_staging_data_sub_account(
    admin: EnterpriseAdmin, sub_account: SubAccount, db: Session
):
    """Clear sub-account's staging data."""
    creds = ensure_creds(admin, db)
    try:
        sheets_service = build("sheets", "v4", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)
        staging_sheet, _ = get_sub_account_bulk_sheet_names(sub_account)

        res = (
            sheets_service.spreadsheets()
            .values()
            .get(
                spreadsheetId=admin.google_spreadsheet_id, range=f"{staging_sheet}!A:A"
            )
            .execute()
        )
        rows = res.get("values", [])

        for row in rows:
            if row and row[0]:
                try:
                    drive_service.files().delete(fileId=row[0]).execute()
                except:
                    pass

        sheets_service.spreadsheets().values().clear(
            spreadsheetId=admin.google_spreadsheet_id, range=f"{staging_sheet}!A:B"
        ).execute()
    except HttpError as e:
        handle_google_api_error(e, "Clearing Session")


def clear_staging_data(user: User, db: Session):
    creds = ensure_creds(user, db)
    try:
        sheets_service = build("sheets", "v4", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        res = (
            sheets_service.spreadsheets()
            .values()
            .get(
                spreadsheetId=user.google_spreadsheet_id,
                range=f"{STAGING_SHEET_NAME}!A:A",
            )
            .execute()
        )
        rows = res.get("values", [])

        for row in rows:
            if row and row[0]:
                try:
                    drive_service.files().delete(fileId=row[0]).execute()
                except:
                    pass

        sheets_service.spreadsheets().values().clear(
            spreadsheetId=user.google_spreadsheet_id, range=f"{STAGING_SHEET_NAME}!A:B"
        ).execute()
    except HttpError as e:
        handle_google_api_error(e, "Clearing Session")


# ==========================================
# BULK PROCESSING (BACKGROUND WORKER)
# ==========================================


def process_bulk_queue_sync(
    user: User,
    db: Session,
    process_func: Callable[[bytes], dict],
    email_func: Optional[Callable[[User, Session, dict], None]] = None,
):
    print(f"--- Starting Bulk Processing for {user.email} ---")
    creds = get_google_creds(user, db)
    if not creds:
        return

    sheets_service = build("sheets", "v4", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    while True:
        try:
            res = (
                sheets_service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=user.google_spreadsheet_id,
                    range=f"{QUEUE_SHEET_NAME}!A1:B1",
                )
                .execute()
            )
            rows = res.get("values", [])

            if not rows:
                break

            file_id = rows[0][0]
            print(f"Processing Bulk File ID: {file_id}")

            try:
                request = drive_service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                fh.seek(0)
                image_bytes = fh.read()
            except Exception as e:
                print(f"Failed to download {file_id}: {e}")
                delete_top_row(sheets_service, user.google_spreadsheet_id)
                continue

            contact_data = process_func(image_bytes)
            if isinstance(contact_data, list):
                contact_data = contact_data[0] if len(contact_data) > 0 else {}
            if not isinstance(contact_data, dict):
                contact_data = {}

            # NEW ROW STRUCTURE: Added Business Category (cat)
            cat_str = (
                ", ".join(contact_data.get("cat", []))
                if contact_data.get("cat")
                else ""
            )
            row_data = [
                force_text(", ".join(contact_data.get("fn", []))),
                force_text(contact_data.get("org", "")),
                force_text(", ".join(contact_data.get("tel", []))),
                force_text(contact_data.get("title", "")),
                force_text(", ".join(contact_data.get("email", []))),
                force_text(", ".join(contact_data.get("url", []))),
                force_text(", ".join(contact_data.get("adr", []))),
                force_text("Bulk Import"),
                force_text(cat_str),
                force_text(contact_data.get("notes", "")),
            ]

            append_to_sheet(user, db, row_data)

            if user.email_feature_enabled and email_func and contact_data.get("email"):
                try:
                    email_func(user, db, contact_data)
                except:
                    pass

            try:
                drive_service.files().delete(fileId=file_id).execute()
            except:
                pass

            delete_top_row(sheets_service, user.google_spreadsheet_id)

        except Exception as e:
            print(f"CRITICAL ERROR processing bulk item: {e}")
            break


def process_bulk_queue_sync_sub_account(
    admin: EnterpriseAdmin,
    sub_account: SubAccount,
    db: Session,
    process_func: Callable[[bytes], dict],
    template: Optional[Dict[str, Any]] = None,
):
    """
    Process bulk queue for a sub-account.
    Saves to sub-account's sheet and uses assigned template for emails.
    """
    print(f"--- Starting Bulk Processing for Sub-Account {sub_account.email} ---")
    creds = get_google_creds(admin, db)
    if not creds:
        return

    sheets_service = build("sheets", "v4", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    staging_sheet, queue_sheet = get_sub_account_bulk_sheet_names(sub_account)

    while True:
        try:
            res = (
                sheets_service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=admin.google_spreadsheet_id,
                    range=f"{queue_sheet}!A1:B1",
                )
                .execute()
            )
            rows = res.get("values", [])

            if not rows:
                break

            file_id = rows[0][0]
            print(f"Processing Bulk File ID: {file_id}")

            try:
                request = drive_service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                fh.seek(0)
                image_bytes = fh.read()
            except Exception as e:
                print(f"Failed to download {file_id}: {e}")
                delete_top_row_from_sheet(
                    sheets_service, admin.google_spreadsheet_id, queue_sheet
                )
                continue

            contact_data = process_func(image_bytes)
            if isinstance(contact_data, list):
                contact_data = contact_data[0] if len(contact_data) > 0 else {}
            if not isinstance(contact_data, dict):
                contact_data = {}

            # Build row data
            cat_str = (
                ", ".join(contact_data.get("cat", []))
                if contact_data.get("cat")
                else ""
            )
            row_data = [
                force_text(", ".join(contact_data.get("fn", []))),
                force_text(contact_data.get("org", "")),
                force_text(", ".join(contact_data.get("tel", []))),
                force_text(contact_data.get("title", "")),
                force_text(", ".join(contact_data.get("email", []))),
                force_text(", ".join(contact_data.get("url", []))),
                force_text(", ".join(contact_data.get("adr", []))),
                force_text("Bulk Import"),
                force_text(cat_str),
                force_text(contact_data.get("notes", "")),
            ]

            # Append to sub-account's sheet
            append_to_sub_account_sheet(admin, sub_account, db, row_data)

            # Send email if template is assigned
            if template and contact_data.get("email"):
                try:
                    # Use the assigned template to send email
                    from backend.main import (
                        normalize_emails,
                        generate_email_prompt,
                        send_gmail,
                    )
                    from litellm import completion

                    emails = normalize_emails(contact_data.get("email", []))
                    if emails:
                        prompt = generate_email_prompt(template, contact_data)
                        response = completion(
                            model="gemini/gemini-flash-lite-latest",
                            messages=[{"role": "user", "content": prompt}],
                            response_format={"type": "json_object"},
                        )
                        content = json.loads(
                            response.choices[0]
                            .message.content.replace("```json", "")
                            .replace("```", "")
                        )

                        for email_addr in emails:
                            try:
                                send_gmail(
                                    admin,
                                    db,
                                    email_addr,
                                    content["subject"],
                                    content["body"],
                                )
                            except:
                                pass
                except:
                    pass

            # Delete file from Drive
            try:
                drive_service.files().delete(fileId=file_id).execute()
            except:
                pass

            # Delete processed row
            delete_top_row_from_sheet(
                sheets_service, admin.google_spreadsheet_id, queue_sheet
            )

        except Exception as e:
            print(f"CRITICAL ERROR processing bulk item: {e}")
            break


def delete_top_row(service, spreadsheet_id):
    """Delete top row from the default QUEUE_SHEET_NAME."""
    delete_top_row_from_sheet(service, spreadsheet_id, QUEUE_SHEET_NAME)


def delete_top_row_from_sheet(service, spreadsheet_id, sheet_name):
    """Delete top row from a specific sheet."""
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheet_id = next(
            s["properties"]["sheetId"]
            for s in meta["sheets"]
            if s["properties"]["title"] == sheet_name
        )
        req = {
            "deleteDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": 0,
                    "endIndex": 1,
                }
            }
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": [req]}
        ).execute()
    except:
        pass


# ==========================================
# CONTACT MANAGEMENT (SINGLE)
# ==========================================


def append_to_sheet(user: User, db: Session, row_data: list):
    creds = ensure_creds(user, db)
    service = build("sheets", "v4", credentials=creds)

    # --- MIGRATION CHECK ---
    # Before appending, check if sheet needs column update
    ensure_schema_v2(service, user.google_spreadsheet_id)

    try:
        body = {"values": [row_data]}
        service.spreadsheets().values().append(
            spreadsheetId=user.google_spreadsheet_id,
            range="A1",
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()
        return "Appended"

    except HttpError as e:
        if e.resp.status == 404:
            print("Sheet missing (404). Recreating infrastructure...")
            new_id = create_spreadsheet_in_folder(creds)
            if new_id:
                user.google_spreadsheet_id = new_id
                db.add(user)
                if safe_commit(db):
                    append_to_sheet(user, db, row_data)
                    return "Recreated"

        handle_google_api_error(e, "Saving Contact")


# ==========================================
# EMAIL & TEMPLATE MANAGEMENT
# ==========================================


def get_or_create_template_sheet(service, spreadsheet_id):
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = sheet_metadata.get("sheets", "")
    for s in sheets:
        if s["properties"]["title"] == TEMPLATE_SHEET_NAME:
            return

    req = {"addSheet": {"properties": {"title": TEMPLATE_SHEET_NAME}}}
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body={"requests": [req]}
    ).execute()

    headers = ["ID", "Subject", "Body", "Is Active", "Attachments"]
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{TEMPLATE_SHEET_NAME}!A1",
        valueInputOption="RAW",
        body={"values": [headers]},
    ).execute()


def fetch_templates(user: User, db: Session):
    creds = ensure_creds(user, db)
    try:
        service = build("sheets", "v4", credentials=creds)
        get_or_create_template_sheet(service, user.google_spreadsheet_id)

        result = (
            service.spreadsheets()
            .values()
            .get(
                spreadsheetId=user.google_spreadsheet_id,
                range=f"{TEMPLATE_SHEET_NAME}!A2:E",
            )
            .execute()
        )

        rows = result.get("values", [])
        templates = []
        for idx, row in enumerate(rows):
            if len(row) < 3:
                continue
            templates.append(
                {
                    "row_id": idx + 2,
                    "id": row[0],
                    "subject": row[1],
                    "body": row[2],
                    "active": row[3] if len(row) > 3 else "FALSE",
                    "attachment": row[4] if len(row) > 4 else "",
                }
            )
        return templates
    except HttpError as e:
        handle_google_api_error(e, "Fetching Templates")


def add_template(
    user, db: Session, subject: str, body: str, attachments: list[dict] = None
):
    """
    Adds a new email template. Works with User or EnterpriseAdmin.
    No limit on number of templates (removed 5-template limit).
    Supports multiple attachments (max 20MB total).
    Attachments are stored in Google Drive to avoid 50k char/cell limit.
    """
    creds = ensure_creds(user, db)
    try:
        sheets_service = build("sheets", "v4", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        import uuid
        import json

        new_id = str(uuid.uuid4())[:8]

        # Upload attachments to Drive if they exist
        attachment_refs = []
        if attachments:
            app_folder_id = get_or_create_app_folder(drive_service)
            attachment_refs = upload_template_attachments_to_drive(
                drive_service, attachments, app_folder_id
            )

        # Store only file references (not base64 data) in Sheets
        attachments_json = json.dumps(attachment_refs) if attachment_refs else ""
        row = [new_id, subject, body, "FALSE", attachments_json]

        sheets_service.spreadsheets().values().append(
            spreadsheetId=user.google_spreadsheet_id,
            range=f"{TEMPLATE_SHEET_NAME}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()
        return {"status": "created", "id": new_id}
    except HttpError as e:
        handle_google_api_error(e, "Creating Template")


def update_template_content(
    user: User,
    db: Session,
    row_id: int,
    subject: str,
    body: str,
    attachments: list[dict] = None,
):
    """
    Updates template content. If attachments are provided, they replace existing attachments.
    Old attachment files are deleted from Drive, new ones are uploaded.
    """
    creds = ensure_creds(user, db)
    try:
        import json

        sheets_service = build("sheets", "v4", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        # Get existing template to find old attachments
        result = (
            sheets_service.spreadsheets()
            .values()
            .get(
                spreadsheetId=user.google_spreadsheet_id,
                range=f"{TEMPLATE_SHEET_NAME}!E{row_id}",
            )
            .execute()
        )

        # Delete old attachment files from Drive
        old_attachments_json = result.get("values", [[]])[0]
        if old_attachments_json and old_attachments_json[0]:
            try:
                old_refs = json.loads(old_attachments_json[0])
                for ref in old_refs:
                    file_id = ref.get("drive_file_id")
                    if file_id:
                        try:
                            drive_service.files().delete(fileId=file_id).execute()
                        except:
                            pass  # File might already be deleted
            except:
                pass  # Old format might not be parseable

        # Upload new attachments to Drive if provided
        attachment_refs = []
        if attachments:
            app_folder_id = get_or_create_app_folder(drive_service)
            attachment_refs = upload_template_attachments_to_drive(
                drive_service, attachments, app_folder_id
            )

        # Update template with new file references
        attachments_json = json.dumps(attachment_refs) if attachment_refs else ""
        sheets_service.spreadsheets().values().update(
            spreadsheetId=user.google_spreadsheet_id,
            range=f"{TEMPLATE_SHEET_NAME}!B{row_id}:E{row_id}",
            valueInputOption="USER_ENTERED",
            body={"values": [[subject, body, "", attachments_json]]},
        ).execute()
        return {"status": "updated"}
    except HttpError as e:
        handle_google_api_error(e, "Updating Template")


def set_active_template(user: User, db: Session, target_row_id: int, make_active: bool):
    creds = ensure_creds(user, db)
    try:
        service = build("sheets", "v4", credentials=creds)
        templates = fetch_templates(user, db)
        data = []
        for t in templates:
            val = "FALSE"
            if t["row_id"] == target_row_id and make_active:
                val = "TRUE"
            data.append(
                {"range": f"{TEMPLATE_SHEET_NAME}!D{t['row_id']}", "values": [[val]]}
            )

        service.spreadsheets().values().batchUpdate(
            spreadsheetId=user.google_spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": data},
        ).execute()
        return {"status": "updated"}
    except HttpError as e:
        handle_google_api_error(e, "Activating Template")


def send_gmail(
    user: User,
    db: Session,
    to_email: str,
    subject: str,
    body_html: str,
    attachments: list[dict] = None,
):
    """
    Send email via Gmail API with optional attachments.

    Args:
        user: User or EnterpriseAdmin object
        db: Database session
        to_email: Recipient email address
        subject: Email subject
        body_html: Email body (HTML format)
        attachments: Optional list of dicts with 'filename', 'data' (base64), and 'size'
    """
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email import encoders
    import mimetypes

    creds = ensure_creds(user, db)
    try:
        service = build("gmail", "v1", credentials=creds)

        # Create multipart message if attachments exist
        if attachments and len(attachments) > 0:
            message = MIMEMultipart()
            message["to"] = to_email
            message["subject"] = subject

            # Attach HTML body
            html_part = MIMEText(body_html, "html")
            message.attach(html_part)

            # Attach all files
            for attachment in attachments:
                if not attachment.get("data"):
                    continue

                filename = attachment.get("filename", "attachment")
                file_data = base64.b64decode(attachment["data"])

                # Determine MIME type
                mime_type, _ = mimetypes.guess_type(filename)
                if mime_type:
                    main_type, sub_type = mime_type.split("/", 1)
                else:
                    main_type, sub_type = "application", "octet-stream"

                # Create attachment part
                attachment_part = MIMEBase(main_type, sub_type)
                attachment_part.set_payload(file_data)
                encoders.encode_base64(attachment_part)
                attachment_part.add_header(
                    "Content-Disposition", f'attachment; filename="{filename}"'
                )
                message.attach(attachment_part)
        else:
            # Simple email without attachment
            message = MIMEText(body_html, "html")
            message["to"] = to_email
            message["subject"] = subject

        # Send the message
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except HttpError as e:
        handle_google_api_error(e, "Sending Email")


# ==========================================
# ENTERPRISE FEATURES: SUB-ACCOUNT SHEET MANAGEMENT
# ==========================================


def create_sub_account_sheet(
    admin: EnterpriseAdmin, sub_account: SubAccount, db: Session
):
    """
    Creates a dedicated sheet for a sub-account within the admin's spreadsheet.
    Sheet name format: "SubAccount_{username}"
    """
    creds = ensure_creds(admin, db)
    try:
        service = build("sheets", "v4", credentials=creds)

        # Generate sheet name
        sheet_name = f"SubAccount_{sub_account.email}"

        # Check if sheet already exists
        meta = (
            service.spreadsheets()
            .get(spreadsheetId=admin.google_spreadsheet_id)
            .execute()
        )
        existing_titles = [s["properties"]["title"] for s in meta.get("sheets", [])]

        if sheet_name not in existing_titles:
            # Create new sheet
            req = {"addSheet": {"properties": {"title": sheet_name}}}
            service.spreadsheets().batchUpdate(
                spreadsheetId=admin.google_spreadsheet_id, body={"requests": [req]}
            ).execute()

            # Add headers to the new sheet
            service.spreadsheets().values().update(
                spreadsheetId=admin.google_spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                body={"values": [HEADERS_V2]},
            ).execute()

            print(f"✅ Created sheet for sub-account: {sheet_name}")

        # Also create bulk sheets for this sub-account
        staging_sheet = f"{sheet_name}_Not_Submitted"
        queue_sheet = f"{sheet_name}_Bulk_Submitted"

        if staging_sheet not in existing_titles:
            req = {"addSheet": {"properties": {"title": staging_sheet}}}
            service.spreadsheets().batchUpdate(
                spreadsheetId=admin.google_spreadsheet_id, body={"requests": [req]}
            ).execute()

        if queue_sheet not in existing_titles:
            req = {"addSheet": {"properties": {"title": queue_sheet}}}
            service.spreadsheets().batchUpdate(
                spreadsheetId=admin.google_spreadsheet_id, body={"requests": [req]}
            ).execute()

        # Update sub-account record with sheet name
        sub_account.sheet_name = sheet_name
        db.add(sub_account)
        if not safe_commit(db):
            raise HTTPException(
                status_code=500, detail="Failed to save sub-account sheet"
            )

        return sheet_name
    except HttpError as e:
        handle_google_api_error(e, "Creating Sub-Account Sheet")


def append_to_sub_account_sheet(
    admin: EnterpriseAdmin, sub_account: SubAccount, db: Session, row_data: list
):
    """
    Appends contact data to a sub-account's dedicated sheet within admin's spreadsheet.
    """
    creds = ensure_creds(admin, db)
    service = build("sheets", "v4", credentials=creds)

    # Ensure admin has a spreadsheet
    if not admin.google_spreadsheet_id:
        ssid = create_spreadsheet_in_folder(creds)
        if ssid:
            admin.google_spreadsheet_id = ssid
            db.add(admin)
            if not safe_commit(db):
                raise HTTPException(
                    status_code=500, detail="Failed to save spreadsheet ID"
                )

    # Ensure sheet exists for this sub-account
    if not sub_account.sheet_name:
        create_sub_account_sheet(admin, sub_account, db)

    # Refresh the sheet_name in case it was just created
    try:
        db.refresh(sub_account)
    except Exception as refresh_error:
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh sub-account: {refresh_error}"
        )
    sheet_name = sub_account.sheet_name

    try:
        body = {"values": [row_data]}
        service.spreadsheets().values().append(
            spreadsheetId=admin.google_spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()
        return "Appended"
    except HttpError as e:
        handle_google_api_error(e, "Saving Contact to Sub-Account Sheet")


def export_sheet_as_excel(
    admin: EnterpriseAdmin, db: Session, sheet_name: Optional[str] = None
):
    """
    Exports a specific sheet or entire spreadsheet as Excel.
    If sheet_name is None, exports entire spreadsheet.
    If sheet_name is provided, exports only that specific sheet.
    """
    creds = ensure_creds(admin, db)
    try:
        drive_service = build("drive", "v3", credentials=creds)

        if sheet_name:
            # Export specific sheet only
            # We need to create a temporary copy with only that sheet
            sheets_service = build("sheets", "v4", credentials=creds)

            # Get the source sheet ID
            meta = (
                sheets_service.spreadsheets()
                .get(spreadsheetId=admin.google_spreadsheet_id)
                .execute()
            )
            source_sheet_id = None
            for s in meta.get("sheets", []):
                if s["properties"]["title"] == sheet_name:
                    source_sheet_id = s["properties"]["sheetId"]
                    break

            if not source_sheet_id:
                raise HTTPException(
                    status_code=404, detail=f"Sheet '{sheet_name}' not found"
                )

            # Create temporary spreadsheet
            temp_ss = (
                sheets_service.spreadsheets()
                .create(body={"properties": {"title": f"Temp_{sheet_name}"}})
                .execute()
            )
            temp_ss_id = temp_ss["spreadsheetId"]

            # Copy sheet to temp spreadsheet
            copy_req = {"destinationSpreadsheetId": temp_ss_id}
            sheets_service.spreadsheets().sheets().copyTo(
                spreadsheetId=admin.google_spreadsheet_id,
                sheetId=source_sheet_id,
                body=copy_req,
            ).execute()

            # Delete the default "Sheet1" from temp spreadsheet
            temp_meta = (
                sheets_service.spreadsheets().get(spreadsheetId=temp_ss_id).execute()
            )
            for s in temp_meta.get("sheets", []):
                if s["properties"]["title"] == "Sheet1":
                    delete_req = {
                        "deleteSheet": {"sheetId": s["properties"]["sheetId"]}
                    }
                    sheets_service.spreadsheets().batchUpdate(
                        spreadsheetId=temp_ss_id, body={"requests": [delete_req]}
                    ).execute()
                    break

            # Export temp spreadsheet
            file_data = (
                drive_service.files()
                .export_media(
                    fileId=temp_ss_id,
                    mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                .execute()
            )

            # Delete temp spreadsheet
            drive_service.files().delete(fileId=temp_ss_id).execute()

            return file_data, f"{sheet_name}.xlsx"
        else:
            # Export entire spreadsheet
            file_data = (
                drive_service.files()
                .export_media(
                    fileId=admin.google_spreadsheet_id,
                    mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                .execute()
            )
            return file_data, "Card2Contacts_All_Contacts.xlsx"

    except HttpError as e:
        handle_google_api_error(e, "Exporting Sheet")


def export_combined_contacts(
    admin: EnterpriseAdmin, sub_accounts: List[SubAccount], db: Session
):
    """
    Exports all contact sheets (admin + all sub-accounts) combined into one Excel file.
    Each sheet becomes a separate tab in the Excel file.
    Only exports actual contact sheets, not internal sheets (templates, bulk processing, etc.)
    """
    creds = ensure_creds(admin, db)
    try:
        sheets_service = build("sheets", "v4", credentials=creds)
        drive_service = build("drive", "v3", credentials=creds)

        # Get all sheets from the spreadsheet
        meta = (
            sheets_service.spreadsheets()
            .get(spreadsheetId=admin.google_spreadsheet_id)
            .execute()
        )
        all_sheets = meta.get("sheets", [])

        # Define which sheets to exclude (internal/system sheets)
        exclude_sheets = {
            TEMPLATE_SHEET_NAME,  # Email_Templates
            STAGING_SHEET_NAME,  # Not_Submitted_Bulk
            QUEUE_SHEET_NAME,  # Bulk_Submitted
        }

        # Also exclude sub-account bulk processing sheets
        for sub in sub_accounts:
            if sub.sheet_name:
                exclude_sheets.add(f"{sub.sheet_name}_Not_Submitted")
                exclude_sheets.add(f"{sub.sheet_name}_Bulk_Submitted")

        # Identify contact sheets (Sheet1 for admin + SubAccount_* sheets)
        contact_sheet_ids = []
        for sheet in all_sheets:
            sheet_title = sheet["properties"]["title"]
            if sheet_title not in exclude_sheets:
                contact_sheet_ids.append(sheet["properties"]["sheetId"])

        if not contact_sheet_ids:
            raise HTTPException(status_code=404, detail="No contact sheets found")

        # Create temporary spreadsheet with only contact sheets
        temp_ss = (
            sheets_service.spreadsheets()
            .create(body={"properties": {"title": "Temp_Combined_Contacts"}})
            .execute()
        )
        temp_ss_id = temp_ss["spreadsheetId"]

        # Copy all contact sheets to temp spreadsheet
        for sheet_id in contact_sheet_ids:
            copy_req = {"destinationSpreadsheetId": temp_ss_id}
            sheets_service.spreadsheets().sheets().copyTo(
                spreadsheetId=admin.google_spreadsheet_id,
                sheetId=sheet_id,
                body=copy_req,
            ).execute()

        # Delete the default "Sheet1" from temp spreadsheet if it exists and wasn't copied
        temp_meta = (
            sheets_service.spreadsheets().get(spreadsheetId=temp_ss_id).execute()
        )
        for s in temp_meta.get("sheets", []):
            if (
                s["properties"]["title"] == "Sheet1"
                and len(temp_meta.get("sheets", [])) > 1
            ):
                # Only delete if there are other sheets
                try:
                    delete_req = {
                        "deleteSheet": {"sheetId": s["properties"]["sheetId"]}
                    }
                    sheets_service.spreadsheets().batchUpdate(
                        spreadsheetId=temp_ss_id, body={"requests": [delete_req]}
                    ).execute()
                except:
                    pass  # If deletion fails, it's okay
                break

        # Export temp spreadsheet
        file_data = (
            drive_service.files()
            .export_media(
                fileId=temp_ss_id,
                mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            .execute()
        )

        # Delete temp spreadsheet
        try:
            drive_service.files().delete(fileId=temp_ss_id).execute()
        except:
            pass  # If cleanup fails, it's okay - temp files will be cleaned up eventually

        return file_data, "Card2Contacts_Combined_All_Users.xlsx"
    except HttpError as e:
        handle_google_api_error(e, "Exporting Combined Contacts")
