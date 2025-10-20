#!/usr/bin/env python
"""Limited scan script that processes only the first N files."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dupdetector.lib.database import get_engine, get_sessionmaker, init_db
from dupdetector.services.repository import Repository
from dupdetector.cli import scan
import argparse

def main():
    parser = argparse.ArgumentParser(description="Scan with file limit")
    parser.add_argument("folder", help="Folder to scan")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--limit", type=int, default=99, help="Maximum files to process")
    parser.add_argument("--workers", type=int, default=4, help="Number of worker threads")
    parser.add_argument("--recursive", action="store_true", help="Recurse into subdirectories")

    args = parser.parse_args()

    # Load config to get database URL
    import json
    config_path = args.config or "config.json"
    with open(config_path, 'r') as f:
        config = json.load(f)

    # Initialize database
    db_url = config.get("database", "sqlite:///dupdetector.db")
    print(f"Connecting to database: {db_url}")
    engine = get_engine(db_url)
    init_db(engine)
    Session = get_sessionmaker(engine)
    session = Session()

    # Inject session and limit into args
    args.session = session
    args.file_limit = args.limit

    # Run scan
    try:
        result = scan(args, session=session)
        print(f"\nScan completed with exit code: {result}")
    finally:
        session.close()

if __name__ == "__main__":
    main()
