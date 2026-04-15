#!/usr/bin/env python3
"""Initialise the database: create tables and seed data."""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import AppConfig
from src.db.manager import DatabaseManager


def main() -> None:
    config = AppConfig.from_env()
    print(f"Connecting to {config.db_host}:{config.db_port}/{config.db_name} ...")
    db = DatabaseManager(config)
    try:
        db.setup()
        print("Database setup complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
