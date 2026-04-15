#!/usr/bin/env python3
"""Migration script: Add user_id column to kb_documents table."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import AppConfig
from src.db.manager import DatabaseManager


def main() -> None:
    config = AppConfig.from_env()
    print(f"Connecting to {config.db_host}:{config.db_port}/{config.db_name} ...")
    db = DatabaseManager(config)

    try:
        with db._conn.cursor() as cur:
            # Check if column already exists
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='kb_documents' AND column_name='user_id'
            """)

            if cur.fetchone():
                print("Column 'user_id' already exists in kb_documents. Skipping migration.")
            else:
                print("Adding 'user_id' column to kb_documents...")
                cur.execute("""
                    ALTER TABLE kb_documents
                    ADD COLUMN user_id INT REFERENCES users(id) ON DELETE CASCADE
                """)
                print("Migration complete: user_id column added successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
