#!/usr/bin/env python3
"""
CLI script to securely bootstrap or provision an Administrator account for Nova Credit AI.
Usage:
    python backend/scripts/create_admin.py --email <admin_email> --password "<admin_password>" --name "System Admin"
"""
import sys
import os
import argparse
import uuid
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from backend.app.database.session import init_db, SessionLocal, UserRecord, get_user_by_email
from backend.app.core.security import hash_password


def create_admin_account(email: str, password: str, full_name: str):
    init_db()
    db = SessionLocal()
    try:
        clean_email = email.lower().strip()
        existing = get_user_by_email(db, clean_email)
        if existing:
            existing.role = "ADMIN"
            existing.password_hash = hash_password(password)
            existing.updated_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            print(f"✅ Successfully updated password and permissions for ADMIN user '{clean_email}'.")
            return

        now_str = datetime.now(timezone.utc).isoformat()
        admin_id = "ADMIN-" + uuid.uuid4().hex[:8].upper()
        admin_user = UserRecord(
            id=admin_id,
            email=clean_email,
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            role="ADMIN",
            is_active=True,
            email_verified=True,
            created_at=now_str,
            updated_at=now_str,
        )
        db.add(admin_user)
        db.commit()
        print(f"🚀 Admin account '{clean_email}' (ID: {admin_id}) created successfully!")
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating admin account: {e}")
        sys.exit(1)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Create or promote an Admin account for Nova Credit AI.")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password (min 8 chars)")
    parser.add_argument("--name", default="System Admin", help="Admin full name")

    args = parser.parse_args()

    if len(args.password) < 8:
        print("❌ Error: Password must be at least 8 characters long.")
        sys.exit(1)

    create_admin_account(args.email, args.password, args.name)


if __name__ == "__main__":
    main()
