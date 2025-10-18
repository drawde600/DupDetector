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

            # prefer CWD config.json
            cfg_path = Path.cwd() / "config.json"
            if not cfg_path.exists():
                # fallback to package config
                cfg_path = Path(__file__).resolve().parents[1] / "config.json"

            if cfg_path.exists():
                with cfg_path.open("r", encoding="utf-8") as fh:
                    cfg = json.load(fh)
                    # support both `database` (sqlalchemy URL or sqlite path) and
                    # legacy/Windows-style `dbConn` semicolon MySQL strings
                    db_path = cfg.get("database") or cfg.get("dbConn")
                    if db_path:
                        # If the config value already looks like a DSN (contains ://),
                        # treat it as a full SQLAlchemy URL. Otherwise treat it as a
                        # plain filesystem path and convert to a sqlite URL.
                        # We'll let get_engine() normalize semicolon-style MySQL
                        # strings and plain paths — just pass through the raw value.
                        db_url = db_path
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
            db_path = Path(path_part)
            parent = db_path.parent
            if parent and not parent.exists():
                print(f"Creating parent directory for sqlite DB: {parent}")
                parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # best-effort; continue and let SQLAlchemy raise a clear error if it fails
        pass

    # Normalize DB URL (this will percent-encode credentials for URLs or
    # convert semicolon-style DSNs to SQLAlchemy URLs) before printing/using.
    try:
        from dupdetector.lib.database import normalize_db_url

        db_url = normalize_db_url(db_url)
    except Exception:
        pass

    # Print a masked DB URL for logging (hide password)
    try:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(db_url)
        if parsed.username or parsed.password:
            user = parsed.username or ""
            host = parsed.hostname or ""
            port = f":{parsed.port}" if parsed.port else ""
            safe_netloc = f"{user}:***@{host}{port}"
            safe_parsed = parsed._replace(netloc=safe_netloc)
            safe_url = urlunparse(safe_parsed)
        else:
            safe_url = db_url
    except Exception:
        safe_url = db_url

    print(f"Using database URL: {safe_url}")

    # We'll create the SQLAlchemy engine after a short direct DB check to avoid
    # subtle differences between a pre-created engine and a direct pymysql test.
    # Try a direct DB connection first to produce a clearer diagnostic when auth fails
    try:
        # parse out connection pieces from the normalized URL
        from urllib.parse import urlparse, unquote_plus

        parsed = urlparse(db_url)
        # urlparse may leave credentials percent-encoded; decode them for direct DB drivers
        db_user = unquote_plus(parsed.username) if parsed.username else None
        db_pass = unquote_plus(parsed.password) if parsed.password else None
        db_host = parsed.hostname or "127.0.0.1"
        db_port = parsed.port or 3306
        db_name = parsed.path.lstrip("/") if parsed.path else None

        # print the parsed connection pieces (mask password) for debugging
        try:
            masked_user = db_user or ""
            print(f"Parsed DB connection: user={masked_user}, host={db_host}, port={db_port}, db={db_name}")
        except Exception:
            pass

        # attempt a direct pymysql connection to provide a clearer error if it fails
        try:
            import pymysql

            # short, best-effort test connection
            conn = pymysql.connect(host=db_host, port=int(db_port), user=db_user, password=db_pass, database=db_name, connect_timeout=5)
            conn.close()
        except Exception as inner_e:
            # Print the underlying exception and attempt a helpful fallback when
            # the configured host is 'localhost' (sometimes grants differ for
            # 'localhost' vs '127.0.0.1').
            print("Direct pymysql connection failed:", inner_e)

            # If host is localhost, try connecting explicitly to 127.0.0.1 as a
            # quick diagnostic/workaround. This often changes how the server
            # classifies the client host for grant matching.
            if db_host == "localhost":
                try:
                    import pymysql as _pymysql

                    print("Attempting fallback direct pymysql connection to 127.0.0.1...")
                    conn = _pymysql.connect(host="127.0.0.1", port=int(db_port), user=db_user, password=db_pass, database=db_name, connect_timeout=5)
                    conn.close()
                except Exception as fb_e:
                    print("Fallback pymysql->127.0.0.1 also failed:", fb_e)
                else:
                    print("Fallback pymysql to 127.0.0.1 succeeded. Consider using 127.0.0.1 in your DB URL or adding grants for 'user'@'localhost'.")

            # re-raise to let the outer handler take over
            raise
        else:
            # helpful confirmation when the direct connection attempt worked
            print("Direct pymysql connection succeeded")

        # create engine and then create tables (this is the step that previously raised OperationalError)
        engine = get_engine(db_url)

        # DEBUG: probe engine-level identity to see how the server classifies the
        # SQLAlchemy/pymysql connection. This prints USER(), CURRENT_USER(), and @@hostname
        # which helps compare the engine connection identity against the direct
        # pymysql.connect() test above.
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                try:
                    row = conn.execute(text("SELECT USER(), CURRENT_USER(), @@hostname")).fetchall()
                    print("engine identity ->", row)
                except Exception as _inner:
                    # If the simple identity query fails, print the exception so we can
                    # see whether the engine can't even run a harmless SELECT.
                    print("engine identity query failed:", _inner)
                    raise
        except Exception:
            # let the outer exception handler report the original failure
            raise

        init_db(engine)
    except Exception as e:
        # Provide a clearer, actionable error message for common auth/grant issues.
        try:
            import sqlalchemy
            is_op_err = isinstance(e, sqlalchemy.exc.OperationalError)
        except Exception:
            is_op_err = False

        print("\nERROR: failed to initialize or connect to the database.")
        print("  Using database URL:", safe_url)
        if hasattr(e, 'args'):
            print("  Error details:", e.args)
        else:
            print("  Exception:", repr(e))

        print("\nCommon causes:")
        print("  - bad username/password (unescaped characters like '@' must be percent-encoded)")
        print("  - missing GRANTs for the connecting host (e.g., 'user'@'localhost' vs 'user'@'127.0.0.1')")
        print("  - authentication plugin mismatch (mysql_native_password vs caching_sha2_password)")

        print("\nIf you control the MySQL server, example SQL to create/grant the user (run as root):")
        print("  CREATE DATABASE IF NOT EXISTS `PhotoDB2025v1`;")
        print("  CREATE USER IF NOT EXISTS 'fh_admin'@'127.0.0.1' IDENTIFIED WITH mysql_native_password BY 'SqlP@ss8';")
        print("  GRANT ALL PRIVILEGES ON `PhotoDB2025v1`.* TO 'fh_admin'@'127.0.0.1';")
        print("  FLUSH PRIVILEGES;")
        # If the error looks like a host/grant mismatch and the original URL
        # used 'localhost', try a secondary attempt using '127.0.0.1' to see if
        # that resolves the SQLAlchemy auth error. This will not change the
        # user's files but will print a helpful diagnostic.
        try:
            if "localhost" in db_url:
                alt_url = db_url.replace("localhost", "127.0.0.1")
                print("\nAttempting SQLAlchemy engine with host replaced by 127.0.0.1 for diagnosis...")
                try:
                    alt_engine = get_engine(alt_url)
                    with alt_engine.connect() as conn:
                        try:
                            row = conn.execute("SELECT USER(), CURRENT_USER(), @@hostname").fetchall()
                            print("alt engine identity ->", row)
                        except Exception as qerr:
                            print("alt engine identity query failed:", qerr)
                            raise
                    # If we reached here, attempt to init DB to verify end-to-end
                    try:
                        init_db(alt_engine)
                    except Exception as ie:
                        print("init_db via alt engine failed:", ie)
                        raise
                    print("Success: SQLAlchemy init_db worked when connecting to 127.0.0.1. Consider updating your DB URL to use 127.0.0.1 or adding GRANTs for the 'localhost' host.")
                except Exception as alt_err:
                    print("Alt attempt with 127.0.0.1 failed:", alt_err)
        except Exception:
            # swallow any errors in the diagnostic attempt and re-raise the
            # original exception below so we keep the original traceback.
            pass

        # re-raise so the script exits with non-zero; the full traceback is still available above
        raise
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
