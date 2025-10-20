#!/usr/bin/env python
"""Purge duplicate files from the duplicate folder after verification.

This script:
1. Finds all files in the duplicate_folders from config
2. Marks them as is_deleted=True in the database
3. Updates updated_at timestamp
4. Deletes the physical files from the filesystem

Uses batch database queries for optimal performance.

IMPORTANT: Only use this after you have manually verified that the files
in the duplicate folder are actual duplicates you want to permanently delete.

Usage:
  python scripts/purge_duplicates.py --config config.json [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from dupdetector.lib.database import get_engine, get_sessionmaker, init_db
from dupdetector.lib.duplicate_folders import load_duplicate_folders_from_config
from dupdetector.lib.db_lock import acquire_lock, DryRunLockChecker, LockAcquisitionError
from dupdetector.services.repository import Repository
from dupdetector.models.file import File


def purge_duplicates(
    config_path: str,
    dry_run: bool = False,
    pattern: Optional[str] = None,
    older_than_days: Optional[int] = None,
    drive_filter: Optional[str] = None
) -> int:
    """Purge duplicate files from duplicate folders.

    Args:
        config_path: Path to config.json
        dry_run: If True, show actions without executing
        pattern: Optional glob pattern to filter files
        older_than_days: Optional age filter in days
        drive_filter: Optional drive letter to filter (e.g., "Z:" or "Z")

    Returns:
        Exit code (0 for success, 1 for error)
    """

    # Load config
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load config from {config_path}: {e}")
        return 1

    # Load duplicate folders configuration (supports both new and legacy format)
    try:
        duplicate_folders = load_duplicate_folders_from_config(config)
        print(f"Loaded duplicate folder configuration for {len(duplicate_folders)} drive(s)")
    except ValueError as e:
        print(f"ERROR: Invalid duplicate folder configuration: {e}")
        return 1

    # Collect all duplicate folder paths
    duplicate_dirs = [Path(folder) for folder in duplicate_folders.values()]

    # Filter by drive if specified
    if drive_filter:
        # Normalize drive filter (ensure it has colon, no backslash)
        drive_normalized = drive_filter.rstrip("\\:") + ":"
        print(f"Filtering to drive: {drive_normalized}")

        # Filter duplicate_folders to only the specified drive
        filtered_duplicate_folders = {}
        for drive_key, folder_path in duplicate_folders.items():
            if drive_key.rstrip("\\") == drive_normalized:
                filtered_duplicate_folders[drive_key] = folder_path

        if not filtered_duplicate_folders:
            print(f"ERROR: No duplicate folder configured for drive {drive_normalized}")
            print(f"Available drives: {list(duplicate_folders.keys())}")
            return 1

        duplicate_folders = filtered_duplicate_folders
        duplicate_dirs = [Path(folder) for folder in duplicate_folders.values()]
        print(f"Using duplicate folder for {drive_normalized}: {duplicate_dirs[0]}")

    # Check that at least one duplicate folder exists
    existing_dirs = [d for d in duplicate_dirs if d.exists()]
    if not existing_dirs:
        print(f"ERROR: No duplicate folders exist:")
        for d in duplicate_dirs:
            print(f"  - {d}")
        return 1

    if not drive_filter:
        print(f"Found {len(existing_dirs)} existing duplicate folder(s):")
        for d in existing_dirs:
            print(f"  - {d}")

    # Initialize database
    db_url = config.get("database", "sqlite:///dupdetector.db")
    print(f"Connecting to database: {db_url}")

    try:
        from dupdetector.lib.database import normalize_db_url
        db_url = normalize_db_url(db_url)
    except Exception:
        pass

    engine = get_engine(db_url)
    init_db(engine)
    Session = get_sessionmaker(engine)
    session = Session()

    # Lock handling: dry-run mode checks locks periodically, normal mode acquires lock
    lock_checker = None
    if dry_run:
        # Dry-run mode: check if lock exists at start, then periodically
        lock_checker = DryRunLockChecker(session, "purge", check_interval=60)
        try:
            lock_checker.check_at_start()
            print("[DRY RUN] No active purge operation detected, proceeding...")
        except LockAcquisitionError as e:
            print(f"ERROR: {e}")
            session.close()
            return 1
    else:
        # Normal mode: acquire lock to prevent concurrent purge operations
        print("Acquiring database lock...")
        try:
            with acquire_lock(session, "purge", timeout_seconds=7200):
                print("Database lock acquired for purge operation")
        except LockAcquisitionError as e:
            print(f"ERROR: {e}")
            print("Another purge operation may be running. Please wait and try again.")
            session.close()
            return 1

    print(f"\nScanning duplicate folders...")
    print("Finding files on disk...")

    # Find all files in all duplicate folders
    files_to_purge = []
    for duplicate_dir in existing_dirs:
        print(f"  Scanning: {duplicate_dir}")
        if pattern:
            dir_files = list(duplicate_dir.glob(pattern))
        else:
            dir_files = [f for f in duplicate_dir.iterdir() if f.is_file()]
        files_to_purge.extend(dir_files)
        print(f"    Found {len(dir_files)} file(s)")

    if pattern:
        print(f"  Pattern filter: {pattern}")
    print(f"  Total files found: {len(files_to_purge)}")

    if not files_to_purge:
        print("No files found in duplicate folder.")
        session.close()
        return 0

    # Filter by age if specified
    if older_than_days is not None:
        print(f"Filtering by age: older than {older_than_days} days...")
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        original_count = len(files_to_purge)
        files_to_purge = [
            f for f in files_to_purge
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff_date
        ]
        filtered_count = original_count - len(files_to_purge)
        print(f"  {filtered_count} files skipped (too recent)")
        print(f"  {len(files_to_purge)} files match age criteria")

    if not files_to_purge:
        print("No files match the criteria.")
        session.close()
        return 0

    # Batch database lookup for optimal performance
    print(f"\n{'='*80}")
    print("BUILDING PURGE PLAN")
    print(f"{'='*80}")
    print("Loading file records from database in batch...")

    # Build set of paths to check
    file_paths_to_check = [str(f.resolve()) for f in files_to_purge]

    # Single batch query to get all matching files
    # This is MUCH faster than querying one file at a time
    db_files = session.query(File).filter(
        File.path.in_(file_paths_to_check)
    ).all()

    print(f"  Loaded {len(db_files)} matching records from database")

    # Build lookup dict: path -> File record
    path_to_record = {f.path: f for f in db_files}

    print("Matching files against database records...")
    files_in_db = []
    files_not_in_db = []
    total_bytes = 0

    for file_path in files_to_purge:
        path_str = str(file_path.resolve())
        file_size = file_path.stat().st_size

        if path_str in path_to_record:
            # Found in database
            file_record = path_to_record[path_str]
            files_in_db.append({
                'path': file_path,
                'db_id': file_record.id,
                'size': file_size,
                'record': file_record
            })
            total_bytes += file_size
        else:
            # Orphaned file (on disk but not in DB) - skip these
            files_not_in_db.append({
                'path': file_path,
                'size': file_size
            })

    print(f"  Completed: {len(files_to_purge)} files matched")
    print(f"  Result: {len(files_in_db)} in DB, {len(files_not_in_db)} orphaned (will be skipped)")

    # Show summary
    print(f"\nFiles to purge:")
    print(f"  In database:     {len(files_in_db)}")
    if files_not_in_db:
        print(f"  Not in database: {len(files_not_in_db)} (will be skipped - delete manually)")
    print(f"  Total to purge:  {len(files_in_db)}")
    print(f"  Total size:      {total_bytes:,} bytes ({total_bytes / (1024**2):.2f} MB)")

    # Show first 10 files as examples
    print(f"\nFirst 10 files to purge:")
    for item in files_in_db[:10]:
        print(f"  {item['path'].name} (id={item['db_id']})")

    if len(files_in_db) > 10:
        print(f"  ... and {len(files_in_db) - 10} more files")

    # Warn about orphaned files if any
    if files_not_in_db:
        print(f"\nNote: {len(files_not_in_db)} orphaned files found (not in database).")
        print(f"These will NOT be purged by this script. Delete manually if needed.")
        if len(files_not_in_db) <= 5:
            print(f"Orphaned files:")
            for item in files_not_in_db:
                print(f"  {item['path'].name}")

    # Confirm unless dry-run
    if not dry_run:
        print(f"\n{'='*80}")
        print("WARNING: This will PERMANENTLY DELETE files!")
        print(f"{'='*80}")
        response = input("\nType 'DELETE' to confirm purge: ")
        if response != "DELETE":
            print("Purge cancelled.")
            session.close()
            return 0

    print(f"\n{'='*80}")
    print("PURGING FILES")
    print(f"{'='*80}")

    purged_count = 0
    db_updated_count = 0
    error_count = 0

    # Process files in database
    for idx, item in enumerate(files_in_db, start=1):
        file_path = item['path']
        file_record = item['record']

        # Progress every 100 files
        if idx % 100 == 0:
            print(f"  Progress: {idx}/{len(files_in_db)} files in DB processed...")

        # Periodic lock check for dry-run mode
        if lock_checker:
            try:
                lock_checker.periodic_check()
            except LockAcquisitionError as e:
                print(f"\nERROR: {e}")
                print("Aborting dry-run operation.")
                session.close()
                return 1

        try:
            if dry_run:
                if idx <= 10:  # Only show first 10 in dry-run
                    print(f"[DRY RUN] Would purge: {file_path.name} (id={item['db_id']})")
            else:
                # Mark as deleted in database
                file_record.is_deleted = True
                # updated_at will auto-update via SQLAlchemy onupdate
                session.commit()
                db_updated_count += 1

                # Delete physical file
                file_path.unlink()
                purged_count += 1

                # Show progress
                if idx % 100 == 0 or idx <= 10:
                    print(f"  {idx}/{len(files_in_db)} Purged: {file_path.name} (id={item['db_id']})")

        except Exception as e:
            print(f"  ERROR purging {file_path.name}: {e}")
            session.rollback()
            error_count += 1

    # Summary
    print(f"\n{'='*80}")
    print("PURGE SUMMARY")
    print(f"{'='*80}")

    if dry_run:
        print(f"  [DRY RUN] Would purge: {len(files_in_db)} files")
        print(f"  [DRY RUN] Would update DB: {len(files_in_db)} records")
        if files_not_in_db:
            print(f"  [DRY RUN] Orphaned files skipped: {len(files_not_in_db)}")
    else:
        print(f"  Files deleted: {purged_count}")
        print(f"  Database records marked deleted: {db_updated_count}")
        print(f"  Errors: {error_count}")
        print(f"  Disk space freed: {total_bytes:,} bytes ({total_bytes / (1024**2):.2f} MB)")
        if files_not_in_db:
            print(f"  Orphaned files skipped: {len(files_not_in_db)} (delete manually)")

    session.close()
    return 0 if error_count == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Purge duplicate files from duplicate folders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be purged
  python scripts/purge_duplicates.py --config config.json --dry-run

  # Purge all files in duplicate folder
  python scripts/purge_duplicates.py --config config.json

  # Purge only JPEG files
  python scripts/purge_duplicates.py --config config.json --pattern "*.jpg"

  # Purge files older than 30 days
  python scripts/purge_duplicates.py --config config.json --older-than-days 30

  # Purge only files on Z: drive
  python scripts/purge_duplicates.py --config config.json --drive Z:

  # Combine filters
  python scripts/purge_duplicates.py --config config.json --drive Z: --pattern "*.jpg"

WARNING: This permanently deletes files! Use --dry-run first to verify.
"""
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to config.json"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be purged without deleting"
    )
    parser.add_argument(
        "--pattern",
        help="Glob pattern to filter files (e.g., '*.jpg', '*-dup*.jpg')"
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        help="Only purge files older than N days"
    )
    parser.add_argument(
        "--drive",
        help="Only purge files on specific drive (e.g., 'Z:' or 'Z')"
    )

    args = parser.parse_args()
    return purge_duplicates(
        args.config,
        args.dry_run,
        args.pattern,
        args.older_than_days,
        args.drive
    )


if __name__ == "__main__":
    raise SystemExit(main())
