#!/usr/bin/env python
"""
App Owner Account Creation Script
==================================
Creates an app owner/developer account for accessing the admin dashboard.

Usage:
    python backend/create_app_owner.py

This script will prompt for email, full name, and password to create an app owner account.
"""

import sys
import getpass
from sqlmodel import Session, select

# Add parent directory to path for imports
sys.path.insert(0, '.')

from backend.database import engine, AppOwner, create_db_and_tables, get_password_hash


def create_app_owner():
    """Create a new app owner account interactively."""

    # Ensure tables exist
    create_db_and_tables()

    print("\n" + "="*60)
    print("  App Owner Account Creation")
    print("="*60)
    print("\nThis will create an app owner/developer account for accessing")
    print("the admin dashboard to monitor distributor activity.\n")

    # Get email
    while True:
        email = input("Email address: ").strip()
        if not email or "@" not in email:
            print("❌ Invalid email address. Please try again.")
            continue

        # Check if email already exists
        with Session(engine) as session:
            existing = session.exec(select(AppOwner).where(AppOwner.email == email)).first()
            if existing:
                print(f"❌ An app owner account with email '{email}' already exists.")
                continue
        break

    # Get full name
    while True:
        full_name = input("Full name: ").strip()
        if not full_name:
            print("❌ Full name cannot be empty. Please try again.")
            continue
        break

    # Get password
    while True:
        password = getpass.getpass("Password (min 8 characters): ")
        if len(password) < 8:
            print("❌ Password must be at least 8 characters long.")
            continue

        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("❌ Passwords do not match. Please try again.")
            continue
        break

    # Create the account
    try:
        with Session(engine) as session:
            app_owner = AppOwner(
                email=email,
                full_name=full_name,
                password_hash=get_password_hash(password),
                is_active=True
            )
            session.add(app_owner)
            session.commit()
            session.refresh(app_owner)

            print("\n" + "="*60)
            print("✅ App Owner Account Created Successfully!")
            print("="*60)
            print(f"\nEmail:     {app_owner.email}")
            print(f"Name:      {app_owner.full_name}")
            print(f"ID:        {app_owner.id}")
            print(f"Created:   {app_owner.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print("\n" + "="*60)
            print("\nYou can now login to the admin dashboard at:")
            print("  http://localhost:8000/admin.html")
            print("\nUse the email and password you just created to login.")
            print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Error creating app owner account: {e}")
        sys.exit(1)


def main():
    try:
        create_app_owner()
    except KeyboardInterrupt:
        print("\n\n⚠️  Account creation cancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()
