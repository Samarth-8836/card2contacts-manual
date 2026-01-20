#!/usr/bin/env python
"""
Enterprise Admin Creation Script
=================================
Internal script to create enterprise admin accounts with a license.

Usage:
    python create_enterprise_admin.py --email "admin@company.com" --password "secret123" --license "ENT-XXXXXXXX-XXXXXXXX"
"""

import argparse
import sys

# Add parent directory to path for imports
sys.path.insert(0, '.')

from sqlmodel import Session, select
from backend.database import (
    engine, 
    License, 
    EnterpriseAdmin, 
    create_db_and_tables,
    get_password_hash
)


def create_admin(email: str, password: str, license_key: str) -> bool:
    """Create an enterprise admin linked to a license."""

    # Ensure tables exist
    create_db_and_tables()

    with Session(engine) as session:
        # Check if license exists and is active
        license_stmt = select(License).where(License.license_key == license_key)
        license_record = session.exec(license_stmt).first()

        if not license_record:
            print(f"Error: License key '{license_key}' not found.")
            return False

        if not license_record.is_active:
            print(f"Error: License key '{license_key}' is not active.")
            return False

        # Check if license type is enterprise
        if license_record.license_type != "enterprise":
            print(f"Error: License '{license_key}' is not an enterprise license (type: {license_record.license_type}).")
            return False

        # Check if license is already used by another admin
        admin_check = select(EnterpriseAdmin).where(EnterpriseAdmin.license_id == license_record.id)
        existing_admin = session.exec(admin_check).first()

        if existing_admin:
            print(f"Error: License is already assigned to admin '{existing_admin.email}'.")
            return False

        # Check if email is already taken
        email_check = select(EnterpriseAdmin).where(EnterpriseAdmin.email == email)
        if session.exec(email_check).first():
            print(f"Error: Email '{email}' is already taken.")
            return False

        # Create the enterprise admin
        admin = EnterpriseAdmin(
            email=email,
            password_hash=get_password_hash(password),
            license_id=license_record.id
        )
        session.add(admin)
        session.commit()

        print(f"\n{'=' * 60}")
        print("Enterprise Admin Created Successfully!")
        print(f"{'=' * 60}")
        print(f"  Email:       {email}")
        print(f"  License:     {license_key}")
        print(f"  License ID:  {license_record.id}")
        print(f"{'=' * 60}")
        print("\nThe admin can now log in using the email and password.\n")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Create an enterprise admin account for Card2Contacts"
    )
    parser.add_argument(
        "--email", "-e",
        type=str,
        required=True,
        help="Email address for the enterprise admin"
    )
    parser.add_argument(
        "--password", "-p",
        type=str,
        required=True,
        help="Password for the enterprise admin"
    )
    parser.add_argument(
        "--license", "-l",
        type=str,
        required=True,
        help="Enterprise license key to assign to this admin"
    )

    args = parser.parse_args()

    # Basic email validation
    if "@" not in args.email or "." not in args.email:
        print("Error: Please provide a valid email address")
        sys.exit(1)

    if len(args.password) < 6:
        print("Error: Password must be at least 6 characters")
        sys.exit(1)

    success = create_admin(args.email, args.password, args.license)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
