from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Request, BackgroundTasks
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
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1' 

from backend.database import create_db_and_tables, get_session, User, verify_password, get_password_hash
from backend.google_utils import (
    append_to_sheet, 
    get_google_creds, 
    create_spreadsheet_in_folder, 
    fetch_templates, 
    add_template, 
    set_active_template, 
    update_template_content, 
    send_gmail, 
    stage_bulk_image, 
    submit_bulk_session, 
    clear_staging_data, 
    check_staging_count, 
    process_bulk_queue_sync,
    handle_google_api_error,
    verify_connection_health,
    ensure_creds
)

app = FastAPI()

# ==========================================
# 1. CONFIGURATION
# ==========================================
SECRET_KEY = "CHANGE_THIS_IN_PROD_TO_A_LONG_RANDOM_STRING"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 43200 

os.environ["GEMINI_API_KEY"] = "your-gemini-api-key" # your-gemini-api-key
os.environ["GOOGLE_CLIENT_ID"] = "your-google-client-id.apps.googleusercontent.com"
os.environ["GOOGLE_CLIENT_SECRET"] = "your-google-client-secret"

REDIRECT_URI = "https://192.168.29.234.sslip.io:8000/api/auth/google/callback"

GOOGLE_SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/drive',        
    'https://www.googleapis.com/auth/gmail.modify', 
    'https://www.googleapis.com/auth/gmail.send'
]

LLM_MODEL = "gemini/gemini-flash-lite-latest" 
OCR_SERVICE_URL = "http://localhost:8001/extract"

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
            "description": "Specific business category e.g. Plumbing, Legal, Software, Forex Trading"
        },
        "notes": {"type": ["string", "null"]}
    },
    "required": ["fn"]
}

origins = ["*"]
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

# ==========================================
# 2. DATA MODELS
# ==========================================
class UserLogin(BaseModel):
    email: str
    password: str

class UserCreate(BaseModel):
    email: str
    password: str

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

# ==========================================
# 3. AUTHENTICATION HELPERS & ENDPOINTS
# ==========================================

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        sid = payload.get("sid")
        if not email or not sid: 
            raise HTTPException(status_code=401, detail="Invalid token")
        
        statement = select(User).where(User.email == email)
        user = db.exec(statement).first()
        
        if not user or user.current_session_id != sid:
            raise HTTPException(status_code=401, detail="Session expired")
        
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

@app.post("/api/register")
def register(user_data: UserCreate, db: Session = Depends(get_session)):
    statement = select(User).where(User.email == user_data.email)
    existing_user = db.exec(statement).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(email=user_data.email, password_hash=get_password_hash(user_data.password))
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@app.post("/api/check-status")
def check_user_status(user_data: UserLogin, db: Session = Depends(get_session)):
    statement = select(User).where(User.email == user_data.email)
    user = db.exec(statement).first()
    
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.current_session_id:
        return {"status": "active", "message": "User is currently logged in."}
    return {"status": "inactive", "message": "Ready to login."}

@app.post("/api/login")
def login(user_data: UserLogin, db: Session = Depends(get_session)):
    statement = select(User).where(User.email == user_data.email)
    user = db.exec(statement).first()
    
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session_id = str(uuid.uuid4())
    user.current_session_id = session_id
    db.add(user)
    db.commit()

    access_token = create_access_token(data={"sub": user.email, "sid": session_id})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/me")
def get_user_info(token: str, db: Session = Depends(get_session)):
    user = get_current_user(token, db)
    return {
        "email": user.email,
        "status": "active",
        "google_connected": user.google_connected
    }

@app.post("/api/logout")
def logout(token: str, db: Session = Depends(get_session)):
    try:
        user = get_current_user(token, db)
        user.current_session_id = None
        db.add(user)
        db.commit()
    except: pass 
    return {"message": "Logged out"}

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
    flow = Flow.from_client_config(client_config, scopes=GOOGLE_SCOPES, redirect_uri=REDIRECT_URI)
    auth_url, _ = flow.authorization_url(access_type='offline', include_granted_scopes='true', state="login_flow", prompt='consent')
    return {"auth_url": auth_url}

@app.get("/api/auth/google/link")
def link_google_account(token: str, db: Session = Depends(get_session)):
    get_current_user(token, db) 
    client_config = {
        "web": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config, scopes=GOOGLE_SCOPES, redirect_uri=REDIRECT_URI)
    auth_url, _ = flow.authorization_url(access_type='offline', include_granted_scopes='true', state=token, prompt='consent')
    return {"auth_url": auth_url}

@app.get("/api/auth/google/callback")
def google_callback(state: str, code: str, db: Session = Depends(get_session)):
    try:
        client_config = {
            "web": {
                "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        flow = Flow.from_client_config(client_config, scopes=GOOGLE_SCOPES, redirect_uri=REDIRECT_URI)
        flow.fetch_token(code=code)
        creds = flow.credentials
        user = None

        if state == "login_flow":
            user_info_service = build('oauth2', 'v2', credentials=creds)
            user_info = user_info_service.userinfo().get().execute()
            email = user_info.get('email')
            
            statement = select(User).where(User.email == email)
            user = db.exec(statement).first()
            if not user:
                user = User(email=email, password_hash="GOOGLE_LINKED_ACCOUNT")
                db.add(user)
                db.commit()
                db.refresh(user)
        else:
            user = get_current_user(state, db)

        user.google_access_token = creds.token
        if creds.refresh_token:
            user.google_refresh_token = creds.refresh_token
        user.google_connected = True
        
        if not user.google_spreadsheet_id:
            try:
                from backend.google_utils import create_spreadsheet_in_folder
                ssid = create_spreadsheet_in_folder(creds)
                if ssid: user.google_spreadsheet_id = ssid
            except: pass 

        session_id = str(uuid.uuid4())
        user.current_session_id = session_id
        db.add(user)
        db.commit()

        app_token = create_access_token(data={"sub": user.email, "sid": session_id})
        return RedirectResponse(url=f"/?token={app_token}")

    except Exception as e:
        return {"error": f"Google Auth Failed: {str(e)}"}

@app.get("/api/auth/google/verify")
def verify_google_status(token: str, db: Session = Depends(get_session)):
    """Explicitly checks if the Google token is valid and has permissions."""
    user = get_current_user(token, db)
    if not user.google_connected:
        raise HTTPException(status_code=400, detail="Google Account not connected")
    
    try:
        verify_connection_health(user, db)
        return {"status": "valid", "detail": "Connection Healthy"}
    except HTTPException as e:
        raise e 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 5. CORE PROCESSING LOGIC
# ==========================================

async def async_process_image_logic(image_bytes: bytes, raw_text: str = ""):
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    system_prompt = f"""
    You are an expert data extraction AI.
    Extract contact details into this valid JSON object matching this schema exactly:
    {json.dumps(VCF_SCHEMA)}
    
    CRITICAL: Analyze the business nature (e.g. Plumbing, IT Services, Legal, Forex) based on the text/images and populate the 'cat' field.
    OCR Text Context: {raw_text}
    """
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": system_prompt},
                {"type": "image_url", "image_url": { "url": f"data:image/jpeg;base64,{base64_image}" }}
            ]
        }
    ]
    try:
        response = await acompletion(
            model=LLM_MODEL, messages=messages, response_format={ "type": "json_object" }
        )
        content = response.choices[0].message.content
        if content.startswith("```json"): 
            content = content.replace("```json", "").replace("```", "")
        data = json.loads(content)
        if isinstance(data, list): return data[0] if len(data) > 0 else {}
        return data
    except Exception as e:
        print(f"AI Processing Error: {e}")
        return {}

def sync_process_image_logic(image_bytes: bytes) -> dict:
    raw_text = ""
    try:
        with httpx.Client() as client:
            files = {'file': ('scan.jpg', image_bytes, 'image/jpeg')}
            res = client.post(OCR_SERVICE_URL, files=files, timeout=30.0)
            if res.status_code == 200: raw_text = res.json().get("full_text", "")
    except: pass

    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    system_prompt = f"Extract JSON Schema: {json.dumps(VCF_SCHEMA)}\nAnalyze Business Category (e.g. Plumbing, Legal) into 'cat' field.\nOCR: {raw_text}"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": system_prompt},
                {"type": "image_url", "image_url": { "url": f"data:image/jpeg;base64,{base64_image}" }}
            ]
        }
    ]
    try:
        response = completion(model=LLM_MODEL, messages=messages, response_format={ "type": "json_object" })
        content = response.choices[0].message.content
        if content.startswith("```json"): content = content.replace("```json", "").replace("```", "")
        data = json.loads(content)
        if isinstance(data, list): return data[0] if len(data) > 0 else {}
        return data
    except: return {}

# --- EMAIL LOGIC ---
def normalize_emails(email_input) -> list:
    import re
    if not email_input: return []
    if isinstance(email_input, str): email_input = [email_input]
    valid_emails = []
    email_regex = r"[^@\s]+@[^@\s]+\.[^@\s]+"
    for item in email_input:
        if not item: continue
        parts = re.split(r'[;,\s\n]+', str(item))
        for part in parts:
            part = part.strip().strip(".'\"")
            if part and re.match(email_regex, part): valid_emails.append(part)
    return list(set(valid_emails))

def generate_email_prompt(template, contact_data):
    name = contact_data.get('fn', ['there'])[0] if contact_data.get('fn') else 'there'
    org = contact_data.get('org') or 'your company'
    notes = contact_data.get('notes') or ''
    return f"""
    Write a personalized email based on:
    SUBJECT: {template['subject']}
    INTENT: {template['body']}
    RECIPIENT: Name: {name}, Company: {org}, Notes: {notes}
    Return JSON: {{ "subject": "...", "body": "HTML Body..." }}
    """

async def process_and_send_email(user_email: str, contact_data: dict, db_session: Session):
    statement = select(User).where(User.email == user_email)
    user = db_session.exec(statement).first()
    if not user or not user.email_feature_enabled: return
    emails = normalize_emails(contact_data.get('email', []))
    if not emails: return
    
    try:
        templates = fetch_templates(user, db_session)
        active_tpl = next((t for t in templates if t['active'] == 'TRUE'), None)
        if not active_tpl: return

        prompt = generate_email_prompt(active_tpl, contact_data)
        response = await acompletion(model=LLM_MODEL, messages=[{"role": "user", "content": prompt}], response_format={ "type": "json_object" })
        content = json.loads(response.choices[0].message.content.replace("```json", "").replace("```", ""))
        
        for email_addr in emails:
            try: send_gmail(user, db_session, email_addr, content['subject'], content['body'])
            except: pass
    except: pass

def sync_email_generation_and_send(user: User, db: Session, contact_data: dict):
    emails = normalize_emails(contact_data.get('email', []))
    if not emails: return
    try:
        templates = fetch_templates(user, db)
        active_tpl = next((t for t in templates if t['active'] == 'TRUE'), None)
        if not active_tpl: return
        prompt = generate_email_prompt(active_tpl, contact_data)
        response = completion(model=LLM_MODEL, messages=[{"role": "user", "content": prompt}], response_format={ "type": "json_object" })
        content = json.loads(response.choices[0].message.content.replace("```json", "").replace("```", ""))
        for email_addr in emails:
            try: send_gmail(user, db, email_addr, content['subject'], content['body'])
            except: pass
    except: pass

def background_bulk_worker(user_email: str, db_session: Session):
    statement = select(User).where(User.email == user_email)
    user = db_session.exec(statement).first()
    if not user: return
    process_bulk_queue_sync(user, db_session, process_func=sync_process_image_logic, email_func=sync_email_generation_and_send)

# ==========================================
# 7. SCANNING & BULK ENDPOINTS
# ==========================================

@app.post("/api/scan")
async def scan_card(
    file: UploadFile = File(...), 
    token: str = None, 
    bulk_stage: bool = False,
    db: Session = Depends(get_session)
):
    if not token: raise HTTPException(status_code=401, detail="Missing token")
    user = get_current_user(token, db)
    file_bytes = await file.read()

    # MODE A: BULK STAGING
    if bulk_stage:
        if not user.google_connected: 
            raise HTTPException(status_code=403, detail="Please link Google Account for Bulk Mode.")
        
        try:
            filename = f"bulk_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:4]}.jpg"
            file_id = stage_bulk_image(user, db, file_bytes, filename)
            count = check_staging_count(user, db)
            return {"status": "staged", "count": count, "file_id": file_id}
        except HTTPException as e:
            raise e 
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload Failed: {str(e)}")

    # MODE B: SINGLE SCAN
    raw_text = ""
    try:
        async with httpx.AsyncClient() as client:
            files = {'file': (file.filename, file_bytes, file.content_type)}
            res = await client.post(OCR_SERVICE_URL, files=files, timeout=30.0)
            if res.status_code == 200: raw_text = res.json().get("full_text", "")
    except: pass

    structured_data = await async_process_image_logic(file_bytes, raw_text)
    return {"raw_text": raw_text, "structured": structured_data}

@app.post("/api/bulk/submit")
def submit_bulk(token: str, background_tasks: BackgroundTasks, db: Session = Depends(get_session)):
    user = get_current_user(token, db)
    if not user.google_connected: raise HTTPException(status_code=400, detail="Google not connected")

    try:
        count = submit_bulk_session(user, db)
        if count > 0: background_tasks.add_task(background_bulk_worker, user.email, db)
        return {"status": "submitted", "count": count}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bulk/cancel")
def cancel_bulk(token: str, db: Session = Depends(get_session)):
    user = get_current_user(token, db)
    try:
        clear_staging_data(user, db)
        return {"status": "cleared"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bulk/check")
def check_bulk_status(token: str, db: Session = Depends(get_session)):
    user = get_current_user(token, db)
    if not user.google_connected: return {"count": 0}
    
    try:
        count = check_staging_count(user, db)
        return {"count": count}
    except HTTPException as e:
        raise e
    except: return {"count": 0}

# ==========================================
# 8. CONTACT SAVING & EXPORT
# ==========================================

@app.post("/api/contacts/save")
def save_contact_to_google(
    contact: ContactSave, 
    token: str, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_session)
):
    user = get_current_user(token, db)
    if not user.google_connected:
        return {"status": "skipped", "detail": "Saved locally only (Google not linked)."}

    # Update Row: Add Business Category (cat)
    cat_str = ", ".join(contact.cat) if contact.cat else ""
    row_data = [
        ", ".join(contact.fn), contact.org, ", ".join(contact.tel), 
        contact.title, ", ".join(contact.email), ", ".join(contact.url), 
        ", ".join(contact.adr), "General", cat_str, contact.notes
    ]
    
    try:
        append_to_sheet(user, db, row_data)
        if user.email_feature_enabled and contact.email:
            background_tasks.add_task(process_and_send_email, user.email, contact.dict(), db)
            return {"status": "success", "detail": "Saved to Google Sheet & Email Queued."}
        return {"status": "success", "detail": "Saved to Google Sheet."}
    except HTTPException as e:
        raise e
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/contacts/export")
def export_contacts(token: str, db: Session = Depends(get_session)):
    user = get_current_user(token, db)
    if not user.google_connected: raise HTTPException(status_code=400, detail="Google not connected")
    
    creds = get_google_creds(user, db)
    if not creds: raise HTTPException(status_code=403, detail="Google Auth Revoked")

    try:
        drive_service = build('drive', 'v3', credentials=creds)
        file_data = drive_service.files().export_media(
            fileId=user.google_spreadsheet_id,
            mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ).execute()
        return StreamingResponse(
            io.BytesIO(file_data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=DigiCard_Contacts.xlsx"}
        )
    except HttpError as e:
        handle_google_api_error(e, "Exporting Contacts")

# ==========================================
# 9. EMAIL SETTINGS ENDPOINTS
# ==========================================

@app.get("/api/email/settings")
def get_email_settings(token: str, db: Session = Depends(get_session)):
    user = get_current_user(token, db)
    if not user.google_connected: raise HTTPException(status_code=400, detail="Google not connected")
    
    try:
        templates = fetch_templates(user, db)
        return {"enabled": user.email_feature_enabled, "templates": templates, "count": len(templates)}
    except HTTPException as e: raise e

@app.post("/api/email/toggle")
def toggle_email_feature(enabled: bool, token: str, db: Session = Depends(get_session)):
    user = get_current_user(token, db)
    if enabled:
        try:
            templates = fetch_templates(user, db)
            if not any(t['active'] == 'TRUE' for t in templates):
                raise HTTPException(status_code=400, detail="Please set at least one active template before enabling.")
        except HTTPException as e: raise e

    user.email_feature_enabled = enabled
    db.add(user)
    db.commit()
    return {"status": "success", "enabled": enabled}

@app.post("/api/email/templates")
def create_template_endpoint(tpl: TemplateCreate, token: str, db: Session = Depends(get_session)):
    user = get_current_user(token, db)
    return add_template(user, db, tpl.subject, tpl.body)

@app.put("/api/email/templates/{row_id}")
def update_template_endpoint(row_id: int, tpl: TemplateCreate, token: str, db: Session = Depends(get_session)):
    user = get_current_user(token, db)
    return update_template_content(user, db, row_id, tpl.subject, tpl.body)

@app.post("/api/email/templates/{row_id}/activate")
def activate_template_endpoint(row_id: int, active: bool, token: str, db: Session = Depends(get_session)):
    user = get_current_user(token, db)
    return set_active_template(user, db, row_id, active)

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")