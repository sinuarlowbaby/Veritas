#!/usr/bin/env python3
"""
setup_postgres.py — Verify and initialize PostgreSQL tables for Veritas.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load backend environment
backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(backend_dir / ".env")

sys.path.insert(0, str(backend_dir))

from app.database import engine, init_db, IS_POSTGRES, DB_URL
from sqlalchemy import text

def main():
    print("=" * 60)
    print("Veritas Database Initialization")
    print("=" * 60)
    print(f"Target URL: {DB_URL}")
    print(f"Database dialect: {'PostgreSQL' if IS_POSTGRES else 'SQLite (fallback)'}")
    
    try:
        with engine.connect() as conn:
            res = conn.execute(text("SELECT 1;")).scalar()
            print("✓ Database connectivity verified (SELECT 1 returned 1)")
    except Exception as exc:
        print(f"✗ Database connection failed: {exc}")
        return 1

    print("\nCreating / verifying tables...")
    init_db()
    
    with engine.connect() as conn:
        if IS_POSTGRES:
            tables = conn.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
            )).fetchall()
            print("\nExisting PostgreSQL tables:")
            for t in tables:
                print(f"  - {t[0]}")
        else:
            tables = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table';"
            )).fetchall()
            print("\nExisting SQLite tables:")
            for t in tables:
                print(f"  - {t[0]}")
                
    print("\n✓ Setup completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
