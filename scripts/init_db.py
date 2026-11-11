"""Database initialization script for NSE Pulse.

Creates tables and indexes in PostgreSQL according to defined SQLAlchemy models.
Usage:
    python scripts/init_db.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.settings import get_settings
from app.monitoring.logging_config import setup_logging
from app.storage.models import Base
from app.storage.repository import PostgresRepository
from sqlalchemy import create_engine


def main():
    settings = get_settings()
    setup_logging(log_level=settings.log_level)

    print("Initializing NSE Pulse Database...")
    print(f"Target Database URL: {settings.database_url}")

    try:
        engine = create_engine(settings.database_url, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        print("Successfully created tables:")
        for table_name in Base.metadata.tables.keys():
            print(f"  - {table_name}")
        print("\nDatabase initialization complete!")
    except Exception as exc:
        print(f"\nError initializing database: {exc}")
        print("Ensure PostgreSQL is running and credentials in .env are correct.")
        sys.exit(1)


if __name__ == "__main__":
    main()

