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
    parser.add_argument("--config", help="Path to JSON config file (overrides default detection)")
    parser.add_argument("--db", default=None, help="SQLAlchemy DB URL (if omitted, read from project config.json)")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--extensions")
    parser.add_argument("--min-size", type=int)
    parser.add_argument("--max-size", type=int)
    parser.add_argument("--limit", type=int, help="Limit the number of files to process")
    parser.add_argument("--workers", type=int, help="Number of worker threads to use for hashing (passed to scan)")
    args = parser.parse_args()

    # --- Startup preflight: load effective config and validate runtime deps ---
    try:
        from dupdetector.cli import _load_config

        # Determine which config path to use (CLI override > CWD > package)
        cfg_path = None
        if args.config:
            cfg_path = Path(args.config)
        else:
            cand = Path.cwd() / "config.json"
            if cand.exists():
                cfg_path = cand
            else:
                pkg_cfg = Path(__file__).resolve().parents[1] / "config.json"
                if pkg_cfg.exists():
                    cfg_path = pkg_cfg

        effective_cfg = _load_config(str(cfg_path)) if cfg_path else {}
    except Exception:
        effective_cfg = {}

    # ExifTool required if configured
    try:
        exiftool_path_cfg = effective_cfg.get("exiftool_path") if isinstance(effective_cfg, dict) else None
        if exiftool_path_cfg:
            exiftool_p = Path(exiftool_path_cfg)
            if not exiftool_p.exists():
                print(f"FATAL: exiftool not found at configured path: {exiftool_p}")
                raise SystemExit(2)
    except SystemExit:
        raise
    except Exception:
        # best-effort: continue if check fails unexpectedly
        pass

    # Geodatabase requirement (strict): must exist/reachable if configured
    try:
        geodb_url = None
        if isinstance(effective_cfg, dict) and effective_cfg.get("geodatabase"):
            geodb_url = effective_cfg.get("geodatabase")
        else:
            # Support legacy geocode.local_geonames block
            geocode_block = effective_cfg.get("geocode") if isinstance(effective_cfg, dict) else None
            if geocode_block and geocode_block.get("enabled"):
                providers = geocode_block.get("providers") or ([geocode_block.get("provider")] if geocode_block.get("provider") else [])
                if any(str(p).lower() == "local_geonames" for p in providers):
                    lg = geocode_block.get("local_geonames", {}) or {}
                    host = lg.get("host")
                    user = lg.get("user")
                    db = lg.get("database")
                    port = int(lg.get("port", 3306)) if lg.get("port") else 3306
                    passwd = lg.get("password")
                    if not (host and user and db):
                        print("FATAL: geocode.local_geonames missing required creds in config; aborting.")
                        raise SystemExit(3)
                    # perform a short pymysql check
                    try:
                        import pymysql
                        conn = pymysql.connect(host=host, port=port, user=user, password=passwd, database=db, connect_timeout=5)
                        conn.close()
                    except Exception as e:
                        print(f"FATAL: local_geonames DB not reachable: {e}")
                        raise SystemExit(4)

        # If a top-level geodatabase URL is provided, validate reachability
        if geodb_url:
            try:
                from dupdetector.lib.database import normalize_db_url
                from urllib.parse import urlparse, unquote_plus

                normalized = normalize_db_url(geodb_url)
            except Exception:
                normalized = geodb_url
            try:
                parsed = urlparse(normalized)
                if parsed.scheme and parsed.scheme.startswith("mysql"):
                    import pymysql
                    db_user = unquote_plus(parsed.username) if parsed.username else None
                    db_pass = unquote_plus(parsed.password) if parsed.password else None
                    db_host = parsed.hostname or "127.0.0.1"
                    db_port = parsed.port or 3306
                    db_name = parsed.path.lstrip("/") if parsed.path else None
                    try:
                        conn = pymysql.connect(host=db_host, port=int(db_port), user=db_user, password=db_pass, database=db_name, connect_timeout=5)
                        conn.close()
                    except Exception as e:
                        print(f"FATAL: geodatabase not reachable: {e}")
                        raise SystemExit(4)
            except SystemExit:
                raise
            except Exception:
                print("FATAL: unable to validate geodatabase reachability; aborting.")
                raise SystemExit(4)
    except SystemExit:
        raise
    except Exception:
        print("FATAL: error during geodatabase preflight; aborting.")
        raise SystemExit(4)

    # Quick candidate count (diagnostic): determine folder and options from effective config
    try:
        folder_to_check = Path(args.folder) if args.folder and args.folder != "." else None
        if not folder_to_check and isinstance(effective_cfg, dict):
            mf = effective_cfg.get("media_folders")
            if isinstance(mf, list) and mf:
                folder_to_check = Path(mf[0])
        if not folder_to_check:
            folder_to_check = Path(args.folder or ".")

        exts = None
        if isinstance(effective_cfg, dict) and effective_cfg.get("extensions"):
            exts = {"." + e.lower().lstrip(".") for e in effective_cfg.get("extensions")}
        recursive_check = bool(effective_cfg.get("recursive", False)) if isinstance(effective_cfg, dict) else False
        min_size = int(effective_cfg.get("min_size")) if isinstance(effective_cfg, dict) and effective_cfg.get("min_size") is not None else None
        max_size = int(effective_cfg.get("max_size")) if isinstance(effective_cfg, dict) and effective_cfg.get("max_size") is not None else None

        cand_count = 0
        if folder_to_check.exists():
            if recursive_check:
                iterator = folder_to_check.rglob("*")
            else:
                iterator = folder_to_check.iterdir()
            for p in iterator:
                try:
                    if not p.is_file():
                        continue
                    if exts and p.suffix.lower() not in exts:
                        continue
                    size = p.stat().st_size
                    if min_size is not None and size < min_size:
                        continue
                    if max_size is not None and size > max_size:
                        continue
                    cand_count += 1
                except Exception:
                    continue
        print(f"Preflight: candidate files in '{folder_to_check}': {cand_count}")
    except Exception:
        # non-fatal
        pass

    # determine DB URL: CLI flag overrides config.json.
    # Prefer config.json in the current working directory, then the package config.
    db_url = args.db
    cfg_used_for_db = None
    if not db_url:
        try:
            import json

            # If the user passed --config, prefer that path for DB selection.
            # Use the package CLI helper `_load_config` so we get detailed
            # per-line prints for every config file the script reads.
            from dupdetector.cli import _load_config

            if args.config:
                cfg_path = Path(args.config)
            else:
                # prefer CWD config.json, then package config
                cfg_path = Path.cwd() / "config.json"
                if not cfg_path.exists():
                    cfg_path = Path(__file__).resolve().parents[1] / "config.json"

            if cfg_path and cfg_path.exists():
                cfg_used_for_db = str(cfg_path)
                cfg = _load_config(str(cfg_path)) or {}
                # support both `database` (sqlalchemy URL or sqlite path) and
                # legacy/Windows-style `dbConn` semicolon MySQL strings
                db_path = cfg.get("database") or cfg.get("dbConn")
                if db_path:
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

        # Only attempt a direct pymysql connection for MySQL-style URLs. For
        # sqlite or other backends skip this probe (it causes spurious auth
        # errors when the DSN isn't for MySQL).
        from urllib.parse import urlparse as _urlparse
        scheme = None
        try:
            scheme = _urlparse(db_url).scheme or None
        except Exception:
            scheme = None

        if scheme and scheme.startswith("mysql"):
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
            # Not a MySQL-style URL: skip direct pymysql probe and make that
            # explicit in the logs instead of claiming a successful pymysql
            # connection (which is misleading for sqlite URLs).
            print(f"Skipping direct pymysql probe: DB URL scheme is not MySQL (scheme={scheme})")

        # create engine and then create tables (this is the step that previously raised OperationalError)
        engine = get_engine(db_url)

        # DEBUG: probe engine-level identity to see how the server classifies the
        # connection. Only run MySQL-specific identity queries when the URL
        # indicates a MySQL backend to avoid executing `@@hostname` or other
        # MySQL-only expressions against SQLite (which will fail).
        try:
            from sqlalchemy import text
            if scheme and scheme.startswith("mysql"):
                with engine.connect() as conn:
                    try:
                        row = conn.execute(text("SELECT USER(), CURRENT_USER(), @@hostname")).fetchall()
                        print("engine identity ->", row)
                    except Exception as _inner:
                        print("engine identity query failed:", _inner)
                        raise
            else:
                print(f"Skipping engine identity query: DB URL scheme is not MySQL (scheme={scheme})")
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
    # Note: no startup backfill. Geocoding happens inline during scan when
    # EXIF is extracted and `repo.update_file_from_exif()` is called for each
    # newly-saved EXIF. This avoids modifying historic rows at startup.

    # Prefer --config CLI arg, then config.json in the current working directory;
    # fall back to package config.json
    if args.config:
        cfg_arg = args.config
    else:
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
                from dupdetector.cli import _load_config

                cfg_json = _load_config(str(cfg_arg)) or {}
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
        limit=args.limit,
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
                    try:
                        from dupdetector.cli import _load_config

                        cfg_json = _load_config(str(cfg_arg)) or {}
                        cfg_workers = cfg_json.get("workers")
                        if isinstance(cfg_workers, int):
                            effective_workers = cfg_workers
                    except Exception:
                        effective_workers = None
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
