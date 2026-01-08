#!/usr/bin/env python
"""
Distributor Role Assignment Script
===================================
Internal script to assign distributor role to existing users.

Usage:
    # For single user:
    python assign_distributor_role.py --email "user@example.com"

    # For enterprise admin:
    python assign_distributor_role.py --email "admin@company.com" --type enterprise_admin

    # For sub-account (email field stores username):
    python assign_distributor_role.py --email "sub_user1" --type sub_account
"""

import argparse
import sys

# Add parent directory to path for imports
sys.path.insert(0, '.')

from sqlmodel import Session, select
from backend.database import (
    engine,
    User,
    EnterpriseAdmin,
    SubAccount,
    Distributor,
    create_db_and_tables
)


def assign_distributor_role(email: str, user_type: str) -> bool:
    """Assign distributor role to a user."""

    # Ensure tables exist
    create_db_and_tables()

    with Session(engine) as session:
        user_obj = None
        user_id = None

        # Find the user based on type
        if user_type == "single":
            stmt = select(User).where(User.email == email)
            user_obj = session.exec(stmt).first()
            if user_obj:
                user_id = user_obj.id
                display_name = user_obj.email
        elif user_type == "enterprise_admin":
            stmt = select(EnterpriseAdmin).where(EnterpriseAdmin.email == email)
            user_obj = session.exec(stmt).first()
            if user_obj:
                user_id = user_obj.id
                display_name = user_obj.email
        elif user_type == "sub_account":
            # For sub-accounts, email field stores the username
            stmt = select(SubAccount).where(SubAccount.email == email)
            user_obj = session.exec(stmt).first()
            if user_obj:
                user_id = user_obj.id
                display_name = user_obj.email
        else:
            print(f"Error: Invalid user type '{user_type}'. Must be 'single', 'enterprise_admin', or 'sub_account'.")
            return False

        if not user_obj:
            print(f"Error: User not found with email '{email}' for type '{user_type}'.")
            return False

        # Check if already a distributor
        check_stmt = select(Distributor).where(
            Distributor.user_id == user_id,
            Distributor.user_type == user_type
        )
        existing = session.exec(check_stmt).first()

        if existing:
            if existing.is_active:
                print(f"Error: User '{display_name}' already has an active distributor role.")
                return False
            else:
                # Reactivate existing distributor role
                existing.is_active = True
                session.add(existing)
                session.commit()
                print(f"\n{'=' * 60}")
                print("Distributor Role Reactivated!")
                print(f"{'=' * 60}")
                print(f"  User:        {display_name}")
                print(f"  User Type:   {user_type}")
                print(f"  Status:      Active")
                print(f"{'=' * 60}")
                print("\nThe user can now access the Distributor Dashboard.\n")
                return True

        # Create new distributor role
        distributor = Distributor(
            user_id=user_id,
            user_type=user_type,
            is_active=True
        )
        session.add(distributor)
        session.commit()

        print(f"\n{'=' * 60}")
        print("Distributor Role Assigned Successfully!")
        print(f"{'=' * 60}")
        print(f"  User:        {display_name}")
        print(f"  User Type:   {user_type}")
        print(f"  Status:      Active")
        print(f"{'=' * 60}")
        print("\nThe user can now access the Distributor Dashboard.\n")

        return True


def main():
    parser = argparse.ArgumentParser(
        description="Assign distributor role to an existing user"
    )
    parser.add_argument(
        "--email", "-e",
        type=str,
        required=True,
        help="Email for single user or enterprise admin, or username for sub-account (stored in email field)"
    )
    parser.add_argument(
        "--type", "-t",
        type=str,
        choices=["single", "enterprise_admin", "sub_account"],
        default="single",
        help="User type (default: single)"
    )

    args = parser.parse_args()

    success = assign_distributor_role(args.email, args.type)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
