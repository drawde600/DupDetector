#!/usr/bin/env python
"""Run a scan and persist results to a SQLite DB.

Usage:
  python scripts/run_scan_persist.py [folder] [--db sqlite:///path/to/db] [--recursive]

This script initializes the DB (creates tables), opens a Session, and calls
the project's `scan` function while passing the Session so file rows are saved.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dupdetector.lib.database import get_engine, get_sessionmaker, init_db
from dupdetector.cli import scan
from dupdetector.services.repository import Repository
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default=".")
    parser.add_argument("--db", default=None, help="SQLAlchemy DB URL (if omitted, read from project config.json)")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--extensions")
    parser.add_argument("--min-size", type=int)
    parser.add_argument("--max-size", type=int)
    parser.add_argument("--workers", type=int, help="Number of worker threads to use for hashing (passed to scan)")
    args = parser.parse_args()

    # determine DB URL: CLI flag overrides config.json.
    # Prefer config.json in the current working directory, then the package config.
    db_url = args.db
    if not db_url:
        try:
            import json
            from pathlib import Path

            # prefer CWD config.json
            cfg_path = Path.cwd() / "config.json"
            if not cfg_path.exists():
                # fallback to package config
                cfg_path = Path(__file__).resolve().parents[1] / "config.json"

            if cfg_path.exists():
                with cfg_path.open("r", encoding="utf-8") as fh:
                    cfg = json.load(fh)
                    db_path = cfg.get("database")
                    if db_path:
                        # If the config value already looks like a DSN (contains ://),
                        # treat it as a full SQLAlchemy URL. Otherwise treat it as a
                        # plain filesystem path and convert to a sqlite URL.
                        if "://" in db_path:
                            db_url = db_path
                        else:
                            # normalize backslashes and convert to sqlite URL
                            db_path = db_path.replace("\\", "/")
                            db_url = f"sqlite:///{db_path}"
        except Exception:
            db_url = None

    if not db_url:
        db_url = "sqlite:///dupdetector.db"
    # If db_url refers to a sqlite file, ensure parent directory exists so the file can be created
    try:
        if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:///:memory:"):
            # strip prefix
            path_part = db_url[len("sqlite:///"):]
            # convert to native path separator
            from pathlib import Path

            db_path = Path(path_part)
            parent = db_path.parent
            if parent and not parent.exists():
                print(f"Creating parent directory for sqlite DB: {parent}")
                parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # best-effort; continue and let SQLAlchemy raise a clear error if it fails
        pass

    print(f"Using database URL: {db_url}")

    # create engine and DB (file will be created if needed)
    engine = get_engine(db_url)
    init_db(engine)
    Session = get_sessionmaker(engine)
    session = Session()

    # Prefer config.json in the current working directory; fall back to package config.json
    cwd_cfg = Path.cwd() / "config.json"
    if cwd_cfg.exists():
        cfg_arg = str(cwd_cfg)
    else:
        project_cfg = Path(__file__).resolve().parents[1] / "config.json"
        cfg_arg = str(project_cfg) if project_cfg.exists() else None

    # If the user didn't explicitly pass --recursive, forward None so scan() will use config.json
    recursive_arg = args.recursive if getattr(args, "recursive", False) else None

    # If the caller didn't pass a folder (or passed the default '.'), prefer the first
    # entry of `media_folders` from the chosen config.json when available.
    folder_arg = args.folder
    if (not args.folder) or args.folder == ".":
        if cfg_arg:
            try:
                import json

                with open(cfg_arg, "r", encoding="utf-8") as fh:
                    cfg_json = json.load(fh)
                mf = cfg_json.get("media_folders")
                if isinstance(mf, list) and len(mf) > 0:
                    folder_arg = mf[0]
            except Exception:
                # ignore parsing errors and fall back to args.folder
                pass

    # construct args Namespace similar to CLI and call scan with session
    cli_args = argparse.Namespace(
        folder=folder_arg,
        config=cfg_arg,
        recursive=recursive_arg,
        extensions=args.extensions,
        min_size=args.min_size,
        max_size=args.max_size,
        workers=args.workers,
    )

    repo = Repository(session)

    # determine effective worker count: CLI -> config -> default
    effective_workers = None
    if cli_args.workers is not None:
        effective_workers = cli_args.workers
    else:
        try:
            if cfg_arg:
                import json

                with open(cfg_arg, "r", encoding="utf-8") as fh:
                    cfg_json = json.load(fh)
                cfg_workers = cfg_json.get("workers")
                if isinstance(cfg_workers, int):
                    effective_workers = cfg_workers
        except Exception:
            effective_workers = None
    if effective_workers is None:
        effective_workers = 4

    start = time.perf_counter()
    # scan() will perform the persistence via the provided session/repo via repo.create_file
    exit_code = scan(cli_args, session=session)
    end = time.perf_counter()

    # Summarize counts from DB using repository helpers
    try:
        files = repo.list_files()
        total = len(files)
        duplicates = sum(1 for f in files if getattr(f, "is_duplicate", False))
        added = total - duplicates
    except Exception:
        total = None
        duplicates = None
        added = None

    duration = end - start
    print("\nScan summary:")
    print(f"  worker threads: {effective_workers}")
    print(f"  elapsed time: {duration:.2f} seconds")
    if total is not None:
        print(f"  total files in DB: {total}")
    if added is not None and duplicates is not None:
        print(f"  added (non-duplicates): {added}")
        print(f"  duplicates: {duplicates}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
