#!/usr/bin/env python
"""
License Generation Script
=========================
Internal script to generate license keys for both single and enterprise users.

Usage:
    # Generate enterprise licenses:
    python generate_licenses.py --count 5 --max-subs 10 --type enterprise

    # Generate single user licenses:
    python generate_licenses.py --count 10 --type single

This will generate license keys that can be assigned to users.
"""

import argparse
import uuid
import json
import sys

# Add parent directory to path for imports
sys.path.insert(0, '.')

from sqlmodel import Session
from backend.database import engine, License, create_db_and_tables


def generate_licenses(count: int, license_type: str, max_sub_accounts: int = 1) -> list[str]:
    """Generate and store license keys in the database."""

    # Ensure tables exist
    create_db_and_tables()

    generated_keys = []

    with Session(engine) as session:
        for _ in range(count):
            # Generate a unique license key
            if license_type == "enterprise":
                license_key = f"ENT-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"
                limits = json.dumps({"max_sub_accounts": max_sub_accounts})
            else:  # single
                license_key = f"SGL-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"
                limits = json.dumps({})  # No limits for single user

            # Create license record
            license_record = License(
                license_key=license_key,
                license_type=license_type,
                limits=limits,
                is_active=True
            )
            session.add(license_record)
            generated_keys.append(license_key)

        session.commit()

    return generated_keys


def main():
    parser = argparse.ArgumentParser(
        description="Generate license keys for Card2Contacts (single or enterprise)"
    )
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=1,
        help="Number of licenses to generate (default: 1)"
    )
    parser.add_argument(
        "--type", "-t",
        type=str,
        choices=["single", "enterprise"],
        default="enterprise",
        help="License type: 'single' or 'enterprise' (default: enterprise)"
    )
    parser.add_argument(
        "--max-subs", "-m",
        type=int,
        default=1,
        help="Maximum sub-accounts allowed per enterprise license (default: 1, ignored for single licenses)"
    )

    args = parser.parse_args()

    if args.count < 1:
        print("Error: Count must be at least 1")
        sys.exit(1)

    if args.type == "enterprise" and args.max_subs < 1:
        print("Error: Max sub-accounts must be at least 1 for enterprise licenses")
        sys.exit(1)

    if args.type == "single":
        print(f"\nGenerating {args.count} single user license(s)...\n")
        keys = generate_licenses(args.count, "single")
    else:
        print(f"\nGenerating {args.count} enterprise license(s) with {args.max_subs} max sub-accounts each...\n")
        keys = generate_licenses(args.count, "enterprise", args.max_subs)

    print("=" * 60)
    print(f"Generated {args.type.title()} License Keys:")
    print("=" * 60)
    for i, key in enumerate(keys, 1):
        print(f"  {i}. {key}")
    print("=" * 60)
    print(f"\nTotal: {len(keys)} license(s) created successfully.")
    print("Store these keys securely - they cannot be recovered!\n")


if __name__ == "__main__":
    main()
