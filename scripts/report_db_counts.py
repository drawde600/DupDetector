#!/usr/bin/env python
"""Report counts from the project's files table.

This script reads `config.json` (preferring CWD) to find the `database` DSN
and supports SQLite and SQLAlchemy-compatible DSNs (including MySQL via
`mysql+pymysql://...` if the driver is installed).
"""
import json
from pathlib import Path
from sqlalchemy import create_engine, text


def load_config():
    cwd_cfg = Path.cwd() / "config.json"
    if cwd_cfg.exists():
        return json.load(open(cwd_cfg, "r", encoding="utf-8"))
    pkg_cfg = Path(__file__).resolve().parents[1] / "config.json"
    if pkg_cfg.exists():
        return json.load(open(pkg_cfg, "r", encoding="utf-8"))
    return {}


def main():
    cfg = load_config()
    db = cfg.get("database")
    if not db:
        print("No 'database' key found in config.json")
        raise SystemExit(1)

    # If db is a filesystem path without scheme, assume sqlite file
    if not (db.startswith("sqlite://") or "://" in db):
        # normalize backslashes
        db_path = db.replace("\\", "/")
        db = f"sqlite:///{db_path}"

    engine = create_engine(db, future=True)
    with engine.connect() as conn:
        try:
            total = conn.execute(text("SELECT COUNT(*) FROM files")).scalar()
        except Exception as e:
            print("Error querying files table:", e)
            raise
        phash = conn.execute(text("SELECT COUNT(*) FROM files WHERE photo_hash IS NOT NULL")).scalar()
        dup = conn.execute(text("SELECT COUNT(*) FROM files WHERE is_duplicate=1")).scalar()

    print(f"DB: {db}\nTotal files: {total}\nFiles with photo_hash: {phash}\nMarked duplicates: {dup}")


if __name__ == "__main__":
    raise SystemExit(main())
