"""
Email Utility Module for DigiCard Enterprise
Handles SMTP email sending for OTP verification and password reset.
"""

import smtplib
import secrets
import string
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==============================================================================
# SMTP Configuration
# ==============================================================================

# Hostinger SMTP credentials
SMTP_HOST = "smtp.hostinger.com"
SMTP_PORT = 465
SMTP_USER = "support@card2contacts.com"
SMTP_PASSWORD = "MRf5k8ch3XBJz3U@"
SMTP_FROM = "Card2Contacts <support@card2contacts.com>"

# ==============================================================================
# Email Sending Functions
# ==============================================================================

def send_system_email(to_email: str, subject: str, html_body: str) -> bool:
    """
    Send a transactional email via SMTP.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        html_body: HTML content of the email

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to_email

        # Create HTML part
        html_part = MIMEText(html_body, "html")
        msg.attach(html_part)

        # Connect to SMTP server and send (using SSL for port 465)
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())

        print(f"[EMAIL] Successfully sent email to {to_email}")
        return True

    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email to {to_email}: {str(e)}")
        return False


def send_otp_email(to_email: str, otp_code: str) -> bool:
    """
    Send OTP verification email.

    Args:
        to_email: Recipient email address
        otp_code: 6-digit OTP code

    Returns:
        True if email sent successfully, False otherwise
    """
    subject = "Your DigiCard Login Verification Code"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .otp-code {{ font-size: 32px; font-weight: bold; color: #007bff; letter-spacing: 5px; padding: 20px; background: #f5f5f5; border-radius: 8px; text-align: center; }}
            .warning {{ color: #666; font-size: 14px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Login Verification Code</h2>
            <p>Your one-time verification code is:</p>
            <div class="otp-code">{otp_code}</div>
            <p class="warning">This code expires in 5 minutes. If you did not request this code, please ignore this email.</p>
            <p>- DigiCard Team</p>
        </div>
    </body>
    </html>
    """
    return send_system_email(to_email, subject, html_body)


def send_password_reset_email(to_email: str, new_password: str) -> bool:
    """
    Send password reset email with new temporary password.

    Args:
        to_email: Recipient email address
        new_password: New temporary password

    Returns:
        True if email sent successfully, False otherwise
    """
    subject = "Your DigiCard Password Has Been Reset"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .password {{ font-size: 24px; font-weight: bold; color: #28a745; padding: 15px; background: #f5f5f5; border-radius: 8px; text-align: center; font-family: monospace; }}
            .warning {{ color: #dc3545; font-size: 14px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Password Reset</h2>
            <p>Your password has been reset. Your new temporary password is:</p>
            <div class="password">{new_password}</div>
            <p>Please use this password to log in. You will be prompted to change your password after verification.</p>
            <p class="warning">If you did not request this password reset, please contact support immediately.</p>
            <p>- DigiCard Team</p>
        </div>
    </body>
    </html>
    """
    return send_system_email(to_email, subject, html_body)


def send_account_credentials_email(to_email: str, username: str, password: str, account_type: str) -> bool:
    """
    Send account credentials to newly created users (by distributor).

    Args:
        to_email: Recipient email address
        username: User's username
        password: Temporary password
        account_type: "single" or "enterprise"

    Returns:
        True if email sent successfully, False otherwise
    """
    account_type_display = "Single User" if account_type == "single" else "Enterprise Admin"
    subject = "Welcome to DigiCard - Your Account Credentials"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .credentials {{ background: #f5f5f5; border-radius: 8px; padding: 20px; margin: 20px 0; }}
            .credential-item {{ margin: 10px 0; }}
            .label {{ font-weight: bold; color: #666; }}
            .value {{ font-size: 18px; color: #333; font-family: monospace; }}
            .warning {{ color: #dc3545; font-size: 14px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Welcome to DigiCard!</h2>
            <p>Your {account_type_display} account has been created. Here are your login credentials:</p>
            <div class="credentials">
                <div class="credential-item">
                    <span class="label">Username:</span><br>
                    <span class="value">{username}</span>
                </div>
                <div class="credential-item">
                    <span class="label">Email:</span><br>
                    <span class="value">{to_email}</span>
                </div>
                <div class="credential-item">
                    <span class="label">Temporary Password:</span><br>
                    <span class="value">{password}</span>
                </div>
            </div>
            <p>You can login using either your username or email.</p>
            <p class="warning">For security, you will be required to change your password on your first login.</p>
            <p>- DigiCard Team</p>
        </div>
    </body>
    </html>
    """
    return send_system_email(to_email, subject, html_body)


def send_sub_account_otp_email(admin_email: str, sub_username: str, otp_code: str) -> bool:
    """
    Send OTP for sub-account login to the admin's email.

    Args:
        admin_email: Admin's email address (receives the OTP)
        sub_username: Sub-account username that is logging in
        otp_code: 6-digit OTP code

    Returns:
        True if email sent successfully, False otherwise
    """
    subject = f"DigiCard Sub-Account Login Code - {sub_username}"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .otp-code {{ font-size: 32px; font-weight: bold; color: #007bff; letter-spacing: 5px; padding: 20px; background: #f5f5f5; border-radius: 8px; text-align: center; }}
            .info {{ background: #e7f3ff; padding: 15px; border-radius: 8px; margin: 15px 0; }}
            .warning {{ color: #666; font-size: 14px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Sub-Account Login Verification</h2>
            <div class="info">
                <strong>Sub-account "{sub_username}" is attempting to log in.</strong>
            </div>
            <p>The verification code is:</p>
            <div class="otp-code">{otp_code}</div>
            <p class="warning">This code expires in 5 minutes. Share this code with your sub-account user to complete their login.</p>
            <p>If this login was not expected, you may want to change the sub-account's password.</p>
            <p>- DigiCard Team</p>
        </div>
    </body>
    </html>
    """
    return send_system_email(admin_email, subject, html_body)


def send_distributor_contact_request_email(user_email: str, username: str) -> bool:
    """
    Send notification to distributor network when a user requests callback for license purchase.

    Args:
        user_email: Email of the user requesting callback
        username: Username of the user requesting callback

    Returns:
        True if email sent successfully, False otherwise
    """
    # Email to distributor
    distributor_email = "support@card2contacts.com"
    subject = f"License Purchase Request - {username}"
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .highlight {{ background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; border-radius: 4px; margin: 20px 0; }}
            .user-info {{ background: #f5f5f5; border-radius: 8px; padding: 20px; margin: 20px 0; }}
            .info-item {{ margin: 10px 0; }}
            .label {{ font-weight: bold; color: #666; }}
            .value {{ font-size: 16px; color: #333; font-family: monospace; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>New License Purchase Request</h2>
            <div class="highlight">
                <strong>A user has requested a callback to purchase a DigiCard license.</strong>
            </div>
            <div class="user-info">
                <div class="info-item">
                    <span class="label">Username:</span><br>
                    <span class="value">{username}</span>
                </div>
                <div class="info-item">
                    <span class="label">Email:</span><br>
                    <span class="value">{user_email}</span>
                </div>
            </div>
            <p><strong>Action Required:</strong> Please contact this user to discuss their license requirements and complete the purchase process.</p>
            <p>- DigiCard System</p>
        </div>
    </body>
    </html>
    """
    return send_system_email(distributor_email, subject, html_body)


# ==============================================================================
# Utility Functions
# ==============================================================================

def generate_otp() -> str:
    """
    Generate a 6-digit OTP code.

    Returns:
        6-digit string OTP
    """
    return str(random.randint(100000, 999999))


def generate_random_password(length: int = 12) -> str:
    """
    Generate a random password with letters, digits, and special characters.

    Args:
        length: Password length (default 12)

    Returns:
        Random password string
    """
    # Ensure at least one of each character type
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"

    # Generate password ensuring variety
    password = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%^&*")
    ]

    # Fill the rest
    password.extend(secrets.choice(alphabet) for _ in range(length - 4))

    # Shuffle to randomize positions
    random.shuffle(password)

    return ''.join(password)


def mask_email(email: str) -> str:
    """
    Mask an email address for display (e.g., j***n@example.com).

    Args:
        email: Full email address

    Returns:
        Masked email string
    """
    if not email or '@' not in email:
        return "***@***.***"

    local, domain = email.split('@', 1)

    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]

    return f"{masked_local}@{domain}"
