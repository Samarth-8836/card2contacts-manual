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

from backend.database import User

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/gmail.modify'
]

INTERNAL_FOLDER_NAME = ".Digital_Business_Card_Scanner_Internal_Data"
BULK_IMAGES_FOLDER = "DigiCard_Bulk_Temp_Images"
SHEET_FILENAME = "DigiCard_Contacts"
TEMPLATE_SHEET_NAME = "Email_Templates"
STAGING_SHEET_NAME = "Not_Submitted_Bulk"
QUEUE_SHEET_NAME = "Bulk_Submitted"

# HEADERS CONFIG
# Current Version (10 Cols)
HEADERS_V2 = [
    "Contact Name", "Business Name", "Contact Numbers", "Job Title", 
    "Emails", "Websites", "Address", "Import Source", "Business Category", "AI Notes"
]

# ==========================================
# ERROR HANDLING (USER FRIENDLY)
# ==========================================

def handle_google_api_error(e: HttpError, context: str = "operation"):
    try:
        error_details = json.loads(e.content.decode())
        error_msg = error_details.get('error', {}).get('message', str(e))
        error_reason = error_details.get('error', {}).get('errors', [{}])[0].get('reason', '')
    except:
        error_msg = str(e)
        error_reason = ""

    print(f"⚠️ Google API Error ({context}): {e.resp.status} - {error_msg}")

    if e.resp.status == 401 or "invalid_grant" in error_msg:
        raise HTTPException(
            status_code=401, 
            detail="Your Google session has expired. Please Re-link your account in the Dashboard."
        )

    if e.resp.status == 403:
        if "insufficientPermissions" in error_msg or "insufficient_scope" in error_msg:
             raise HTTPException(
                 status_code=403, 
                 detail="DigiCard lacks permission to access Drive or Sheets. Please Re-link and ensure all checkboxes are checked."
             )
        if "usageLimits" in error_msg:
             raise HTTPException(status_code=429, detail="Google API usage limit exceeded. Please try again later.")
        
        raise HTTPException(
            status_code=403, 
            detail="Google Access Denied. You may have revoked permissions in your Google Account settings."
        )

    if e.resp.status == 404:
        raise HTTPException(
            status_code=404, 
            detail=f"The requested Google file or sheet was not found. It may have been deleted."
        )
    
    if "storageQuotaExceeded" in error_reason:
        raise HTTPException(status_code=507, detail="Your Google Drive storage is full.")

    raise HTTPException(status_code=502, detail=f"Google Error during {context}: {error_msg}")

# ==========================================
# AUTHENTICATION
# ==========================================

def get_google_creds(user: User, db: Session):
    if not user.google_refresh_token:
        return None

    creds = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_uri=user.google_token_uri,
        client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        scopes=SCOPES
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            user.google_access_token = creds.token
            db.add(user)
            db.commit()
        except RefreshError:
            print(f"⚠️ Google Token Revoked for {user.email}. Disconnecting.")
            user.google_connected = False
            user.google_access_token = None
            user.google_refresh_token = None
            db.add(user)
            db.commit()
            return None
        except Exception as e:
            print(f"Token Refresh Network Error: {e}")
            return None
            
    return creds

def ensure_creds(user: User, db: Session):
    creds = get_google_creds(user, db)
    if not creds:
        raise HTTPException(
            status_code=403, 
            detail="Google connection broken. Please Re-link Account."
        )
    return creds

def verify_connection_health(user: User, db: Session):
    creds = ensure_creds(user, db)
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        drive_service.files().list(pageSize=1, fields="files(id)").execute()
        return True
    except HttpError as e:
        handle_google_api_error(e, "Connection Check")

# ==========================================
# DRIVE & FOLDER MANAGEMENT
# ==========================================

def get_or_create_folder(drive_service, folder_name, parent_id=None):
    try:
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])

        if files: 
            return files[0]['id']

        metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
        if parent_id: metadata['parents'] = [parent_id]
        
        folder = drive_service.files().create(body=metadata, fields='id').execute()
        return folder.get('id')
    except HttpError as e:
        handle_google_api_error(e, "Folder Creation")

def get_app_folders(creds):
    try:
        service = build('drive', 'v3', credentials=creds)
        main_id = get_or_create_folder(service, INTERNAL_FOLDER_NAME)
        bulk_id = get_or_create_folder(service, BULK_IMAGES_FOLDER, parent_id=main_id)
        return main_id, bulk_id
    except HttpError as e:
        handle_google_api_error(e, "Folder Setup")

def get_or_create_app_folder(drive_service):
    return get_or_create_folder(drive_service, INTERNAL_FOLDER_NAME)

# ==========================================
# SPREADSHEET INFRASTRUCTURE
# ==========================================

def ensure_bulk_sheets(service, spreadsheet_id):
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        existing_titles = [s['properties']['title'] for s in meta.get('sheets', [])]

        reqs = []
        if STAGING_SHEET_NAME not in existing_titles:
            reqs.append({'addSheet': {'properties': {'title': STAGING_SHEET_NAME}}})
        if QUEUE_SHEET_NAME not in existing_titles:
            reqs.append({'addSheet': {'properties': {'title': QUEUE_SHEET_NAME}}})
        
        if reqs:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id, body={'requests': reqs}
            ).execute()
    except HttpError as e:
        handle_google_api_error(e, "Ensuring Bulk Sheets")

def create_spreadsheet_in_folder(creds):
    try:
        service = build('sheets', 'v4', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)

        folder_id = get_or_create_app_folder(drive_service)
        if not folder_id: return None

        file_metadata = {
            'name': SHEET_FILENAME,
            'parents': [folder_id],
            'mimeType': 'application/vnd.google-apps.spreadsheet'
        }
        
        file = drive_service.files().create(body=file_metadata, fields='id').execute()
        ssid = file.get('id')

        # Create with V2 Headers
        service.spreadsheets().values().update(
            spreadsheetId=ssid, range="A1", valueInputOption="RAW", body={'values': [HEADERS_V2]}
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
        res = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range="A1:Z1"
        ).execute()
        headers = res.get('values', [[]])[0]

        # Check for V2 Signature
        if "Business Category" in headers:
            return # Already V2

        print("--- Migrating Sheet to V2 Schema (Adding Category Column) ---")

        # 2. Get Sheet ID (Integer) for the first sheet (Contacts)
        sheet_meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        # Assuming contacts are on the first sheet
        sheet_id = sheet_meta['sheets'][0]['properties']['sheetId']

        # 3. Batch Update: Insert Column & Update Header
        requests = [
            {
                "insertDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": 8, # Index 8 is Column I
                        "endIndex": 9
                    },
                    "inheritFromBefore": True
                }
            },
            {
                "updateCells": {
                    "rows": [{
                        "values": [{
                            "userEnteredValue": {"stringValue": "Business Category"}
                        }]
                    }],
                    "fields": "userEnteredValue",
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 8,
                        "endColumnIndex": 9
                    }
                }
            }
        ]

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={'requests': requests}
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

def stage_bulk_image(user: User, db: Session, file_obj: bytes, filename: str):
    creds = ensure_creds(user, db)
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        sheets_service = build('sheets', 'v4', credentials=creds)

        _, bulk_folder_id = get_app_folders(creds)
        
        file_metadata = {'name': filename, 'parents': [bulk_folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_obj), mimetype='image/jpeg', resumable=True)
        
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = file.get('id')

        ensure_bulk_sheets(sheets_service, user.google_spreadsheet_id)
        
        row = [file_id, "Pending Upload"]
        sheets_service.spreadsheets().values().append(
            spreadsheetId=user.google_spreadsheet_id,
            range=f"{STAGING_SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={'values': [row]}
        ).execute()
        
        return file_id
    except HttpError as e:
        handle_google_api_error(e, "Staging Image")

def check_staging_count(user: User, db: Session):
    creds = ensure_creds(user, db)
    try:
        service = build('sheets', 'v4', credentials=creds)
        ensure_bulk_sheets(service, user.google_spreadsheet_id)
        
        res = service.spreadsheets().values().get(
            spreadsheetId=user.google_spreadsheet_id, range=f"{STAGING_SHEET_NAME}!A:A"
        ).execute()
        values = res.get('values', [])
        return len(values)
    except HttpError as e:
        handle_google_api_error(e, "Checking Bulk Status")

def submit_bulk_session(user: User, db: Session):
    creds = ensure_creds(user, db)
    try:
        service = build('sheets', 'v4', credentials=creds)
        
        res = service.spreadsheets().values().get(
            spreadsheetId=user.google_spreadsheet_id, range=f"{STAGING_SHEET_NAME}!A:B"
        ).execute()
        rows = res.get('values', [])
        
        if not rows: return 0

        service.spreadsheets().values().append(
            spreadsheetId=user.google_spreadsheet_id,
            range=f"{QUEUE_SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={'values': rows}
        ).execute()

        service.spreadsheets().values().clear(
            spreadsheetId=user.google_spreadsheet_id, range=f"{STAGING_SHEET_NAME}!A:B"
        ).execute()
        
        return len(rows)
    except HttpError as e:
        handle_google_api_error(e, "Submitting Batch")

def clear_staging_data(user: User, db: Session):
    creds = ensure_creds(user, db)
    try:
        sheets_service = build('sheets', 'v4', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)
        
        res = sheets_service.spreadsheets().values().get(
            spreadsheetId=user.google_spreadsheet_id, range=f"{STAGING_SHEET_NAME}!A:A"
        ).execute()
        rows = res.get('values', [])

        for row in rows:
            if row and row[0]:
                try:
                    drive_service.files().delete(fileId=row[0]).execute()
                except: pass

        sheets_service.spreadsheets().values().clear(
            spreadsheetId=user.google_spreadsheet_id, range=f"{STAGING_SHEET_NAME}!A:B"
        ).execute()
    except HttpError as e:
        handle_google_api_error(e, "Clearing Session")

# ==========================================
# BULK PROCESSING (BACKGROUND WORKER)
# ==========================================

def process_bulk_queue_sync(
    user: User, db: Session, process_func: Callable[[bytes], dict],
    email_func: Optional[Callable[[User, Session, dict], None]] = None
):
    print(f"--- Starting Bulk Processing for {user.email} ---")
    creds = get_google_creds(user, db)
    if not creds: return

    sheets_service = build('sheets', 'v4', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)
    
    while True:
        try:
            res = sheets_service.spreadsheets().values().get(
                spreadsheetId=user.google_spreadsheet_id, range=f"{QUEUE_SHEET_NAME}!A1:B1"
            ).execute()
            rows = res.get('values', [])
            
            if not rows: break

            file_id = rows[0][0]
            print(f"Processing Bulk File ID: {file_id}")

            try:
                request = drive_service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False: status, done = downloader.next_chunk()
                fh.seek(0)
                image_bytes = fh.read()
            except Exception as e:
                print(f"Failed to download {file_id}: {e}")
                delete_top_row(sheets_service, user.google_spreadsheet_id)
                continue

            contact_data = process_func(image_bytes)
            if isinstance(contact_data, list): contact_data = contact_data[0] if len(contact_data) > 0 else {}
            if not isinstance(contact_data, dict): contact_data = {}

            # NEW ROW STRUCTURE: Added Business Category (cat)
            cat_str = ", ".join(contact_data.get('cat', [])) if contact_data.get('cat') else ""
            row_data = [
                ", ".join(contact_data.get('fn',[])),  
                contact_data.get('org', ''),            
                ", ".join(contact_data.get('tel',[])), 
                contact_data.get('title', ''),          
                ", ".join(contact_data.get('email',[])),
                ", ".join(contact_data.get('url',[])),
                ", ".join(contact_data.get('adr',[])),
                "Bulk Import",
                cat_str,              
                contact_data.get('notes', '')
            ]
            
            append_to_sheet(user, db, row_data)

            if user.email_feature_enabled and email_func and contact_data.get('email'):
                try: email_func(user, db, contact_data)
                except: pass

            try: drive_service.files().delete(fileId=file_id).execute()
            except: pass

            delete_top_row(sheets_service, user.google_spreadsheet_id)

        except Exception as e:
            print(f"CRITICAL ERROR processing bulk item: {e}")
            break

def delete_top_row(service, spreadsheet_id):
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheet_id = next(s['properties']['sheetId'] for s in meta['sheets'] if s['properties']['title'] == QUEUE_SHEET_NAME)
        req = {"deleteDimension": {"range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 0, "endIndex": 1}}}
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={'requests': [req]}).execute()
    except: pass

# ==========================================
# CONTACT MANAGEMENT (SINGLE)
# ==========================================

def append_to_sheet(user: User, db: Session, row_data: list):
    creds = ensure_creds(user, db)
    service = build('sheets', 'v4', credentials=creds)

    # --- MIGRATION CHECK ---
    # Before appending, check if sheet needs column update
    ensure_schema_v2(service, user.google_spreadsheet_id)

    try:
        body = {'values': [row_data]}
        service.spreadsheets().values().append(
            spreadsheetId=user.google_spreadsheet_id,
            range="A1", valueInputOption="USER_ENTERED", body=body
        ).execute()
        return "Appended"

    except HttpError as e:
        if e.resp.status == 404:
            print("Sheet missing (404). Recreating infrastructure...")
            new_id = create_spreadsheet_in_folder(creds)
            if new_id:
                user.google_spreadsheet_id = new_id
                db.add(user)
                db.commit()
                append_to_sheet(user, db, row_data)
                return "Recreated"
        
        handle_google_api_error(e, "Saving Contact")

# ==========================================
# EMAIL & TEMPLATE MANAGEMENT
# ==========================================

def get_or_create_template_sheet(service, spreadsheet_id):
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = sheet_metadata.get('sheets', '')
    for s in sheets:
        if s['properties']['title'] == TEMPLATE_SHEET_NAME: return

    req = {'addSheet': {'properties': {'title': TEMPLATE_SHEET_NAME}}}
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={'requests': [req]}).execute()
    
    headers = ["ID", "Subject", "Body", "Is Active"]
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=f"{TEMPLATE_SHEET_NAME}!A1", valueInputOption="RAW", body={'values': [headers]}
    ).execute()

def fetch_templates(user: User, db: Session):
    creds = ensure_creds(user, db)
    try:
        service = build('sheets', 'v4', credentials=creds)
        get_or_create_template_sheet(service, user.google_spreadsheet_id)
        
        result = service.spreadsheets().values().get(
            spreadsheetId=user.google_spreadsheet_id, range=f"{TEMPLATE_SHEET_NAME}!A2:D"
        ).execute()
        
        rows = result.get('values', [])
        templates = []
        for idx, row in enumerate(rows):
            if len(row) < 3: continue
            templates.append({
                "row_id": idx + 2,
                "id": row[0],
                "subject": row[1],
                "body": row[2],
                "active": row[3] if len(row) > 3 else "FALSE"
            })
        return templates
    except HttpError as e:
        handle_google_api_error(e, "Fetching Templates")

def add_template(user: User, db: Session, subject: str, body: str):
    creds = ensure_creds(user, db)
    try:
        service = build('sheets', 'v4', credentials=creds)
        current = fetch_templates(user, db)
        if len(current) >= 5: raise HTTPException(400, "Maximum of 5 templates allowed.")

        import uuid
        new_id = str(uuid.uuid4())[:8]
        row = [new_id, subject, body, "FALSE"]
        
        service.spreadsheets().values().append(
            spreadsheetId=user.google_spreadsheet_id, range=f"{TEMPLATE_SHEET_NAME}!A1", valueInputOption="USER_ENTERED", body={'values': [row]}
        ).execute()
        return {"status": "created"}
    except HttpError as e:
        handle_google_api_error(e, "Creating Template")

def update_template_content(user: User, db: Session, row_id: int, subject: str, body: str):
    creds = ensure_creds(user, db)
    try:
        service = build('sheets', 'v4', credentials=creds)
        service.spreadsheets().values().update(
            spreadsheetId=user.google_spreadsheet_id, range=f"{TEMPLATE_SHEET_NAME}!B{row_id}:C{row_id}",
            valueInputOption="USER_ENTERED", body={'values': [[subject, body]]}
        ).execute()
        return {"status": "updated"}
    except HttpError as e:
        handle_google_api_error(e, "Updating Template")

def set_active_template(user: User, db: Session, target_row_id: int, make_active: bool):
    creds = ensure_creds(user, db)
    try:
        service = build('sheets', 'v4', credentials=creds)
        templates = fetch_templates(user, db)
        data = []
        for t in templates:
            val = "FALSE"
            if t['row_id'] == target_row_id and make_active: val = "TRUE"
            data.append({"range": f"{TEMPLATE_SHEET_NAME}!D{t['row_id']}", "values": [[val]]})
            
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=user.google_spreadsheet_id, body={"valueInputOption": "USER_ENTERED", "data": data}
        ).execute()
        return {"status": "updated"}
    except HttpError as e:
        handle_google_api_error(e, "Activating Template")

def send_gmail(user: User, db: Session, to_email: str, subject: str, body_html: str):
    creds = ensure_creds(user, db)
    try:
        service = build('gmail', 'v1', credentials=creds)
        message = MIMEText(body_html, 'html')
        message['to'] = to_email
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
    except HttpError as e:
        handle_google_api_error(e, "Sending Email")