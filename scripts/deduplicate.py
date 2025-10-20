#!/usr/bin/env python
"""Move duplicate files to a designated folder, keeping the file with the lowest ID.

Usage:
  python scripts/deduplicate.py [--config config.json] [--dry-run] [--workers 4]

This script:
1. Queries the database for files with duplicate MD5 hashes
2. Keeps the file with the lowest ID (first seen)
3. Moves all other duplicates to the duplicate_folder specified in config
4. Auto-renames moved files with -dup1, -dup2, etc before extension
5. Updates the database to reflect the new paths
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Optional
from collections import defaultdict

from dupdetector.lib.database import get_engine, get_sessionmaker, init_db
from dupdetector.lib.duplicate_folders import (
    load_duplicate_folders_from_config,
    get_duplicate_folder_for_file,
    validate_duplicate_folders_config
)
from dupdetector.lib.db_lock import acquire_lock, DryRunLockChecker, LockAcquisitionError
from dupdetector.services.repository import Repository
from dupdetector.models.file import File


def get_unique_path(target_dir: Path, filename: str) -> Path:
    """Generate a unique filename by appending -dup1, -dup2, etc.

    Always appends a -dupN suffix to duplicate files, regardless of conflicts.
    This makes it clear that these are duplicate files that were moved.

    Args:
        target_dir: Destination directory
        filename: Original filename

    Returns:
        Unique Path with -dupN suffix that doesn't conflict with existing files

    Examples:
        >>> get_unique_path(Path('/duplicates'), 'IMG_1234.jpg')
        Path('/duplicates/IMG_1234-dup1.jpg')

        >>> get_unique_path(Path('/duplicates'), 'IMG_1234.jpg')
        Path('/duplicates/IMG_1234-dup2.jpg')  # if IMG_1234-dup1.jpg exists
    """
    # Split filename into stem and extension
    stem = Path(filename).stem
    ext = Path(filename).suffix

    # Always append -dupN suffix
    counter = 1
    while True:
        new_filename = f"{stem}-dup{counter}{ext}"
        new_path = target_dir / new_filename
        if not new_path.exists():
            return new_path
        counter += 1


def find_duplicates_by_md5(repo: Repository) -> dict[str, list[File]]:
    """Find all files grouped by MD5 hash.

    Returns:
        Dictionary mapping MD5 hash to list of File objects with that hash
        Only returns groups with 2+ files (actual duplicates)
    """
    # Query all files, group by MD5
    all_files = repo.list_files()

    md5_groups = defaultdict(list)
    for f in all_files:
        if f.md5_hash:
            md5_groups[f.md5_hash].append(f)

    # Filter to only actual duplicates (2+ files with same hash)
    duplicates = {md5: files for md5, files in md5_groups.items() if len(files) > 1}

    return duplicates


def deduplicate_files(
    config_path: str,
    dry_run: bool = False,
    folders: Optional[list[str]] = None
) -> int:
    """Move duplicate files to duplicate_folders, keeping lowest ID.

    Args:
        config_path: Path to config.json
        dry_run: If True, print actions without executing
        folders: Optional list of folders to limit deduplication scope

    Returns:
        Exit code (0 for success)
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
        print(f"Duplicate folder configuration loaded: {len(duplicate_folders)} drive(s)")
        for drive, folder in duplicate_folders.items():
            print(f"  {drive} -> {folder}")
    except ValueError as e:
        print(f"ERROR: Invalid duplicate folder configuration: {e}")
        return 1

    # Validate duplicate folders against media folders
    media_folders = config.get("media_folders", [])
    if media_folders:
        validation_errors = validate_duplicate_folders_config(duplicate_folders, media_folders)
        if validation_errors:
            print("ERROR: Duplicate folder configuration validation failed:")
            for error in validation_errors:
                print(f"  - {error}")
            return 1

    # Create duplicate folders if they don't exist
    if not dry_run:
        for drive, dup_folder in duplicate_folders.items():
            dup_path = Path(dup_folder)
            try:
                dup_path.mkdir(parents=True, exist_ok=True)
                print(f"Ensured duplicate folder exists: {dup_path}")
            except Exception as e:
                print(f"ERROR: Failed to create duplicate folder {dup_path}: {e}")
                return 1

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
        lock_checker = DryRunLockChecker(session, "deduplicate", check_interval=60)
        try:
            lock_checker.check_at_start()
            print("[DRY RUN] No active deduplication operation detected, proceeding...")
        except LockAcquisitionError as e:
            print(f"ERROR: {e}")
            session.close()
            return 1
    else:
        # Normal mode: acquire lock to prevent concurrent deduplication operations
        print("Acquiring database lock...")
        try:
            with acquire_lock(session, "deduplicate", timeout_seconds=7200):
                print("Database lock acquired for deduplication operation")
        except LockAcquisitionError as e:
            print(f"ERROR: {e}")
            print("Another deduplication operation may be running. Please wait and try again.")
            session.close()
            return 1

    repo = Repository(session)

    # Find duplicates
    print("\nFinding duplicates...")
    duplicates = find_duplicates_by_md5(repo)

    if not duplicates:
        print("No duplicates found.")
        return 0

    print(f"Found {len(duplicates)} MD5 groups with duplicates")

    # Filter by folders if specified
    if folders:
        folder_paths = [Path(f).resolve() for f in folders]
        print(f"Filtering to files in folders: {', '.join(str(f) for f in folder_paths)}")

        filtered_duplicates = {}
        for md5, files in duplicates.items():
            # Only include files whose path starts with one of the specified folders
            matching_files = [
                f for f in files
                if any(str(Path(f.path).resolve()).startswith(str(fp)) for fp in folder_paths)
            ]
            if len(matching_files) > 1:
                filtered_duplicates[md5] = matching_files

        duplicates = filtered_duplicates
        print(f"After filtering: {len(duplicates)} MD5 groups")

    # Process each duplicate group
    total_moved = 0
    total_bytes_saved = 0

    for md5, files in duplicates.items():
        # Sort by ID to keep the lowest
        files_sorted = sorted(files, key=lambda f: f.id)

        keeper = files_sorted[0]
        to_move = files_sorted[1:]

        try:
            print(f"\nMD5: {md5}")
        except Exception:
            # Handle console encoding issues on Windows
            print(f"\nMD5: [hash value]")

        try:
            print(f"  Keeping: {keeper.path} (id={keeper.id}, size={keeper.size})")
        except Exception:
            print(f"  Keeping: [path] (id={keeper.id}, size={keeper.size})")

        print(f"  Moving {len(to_move)} duplicate(s):")

        for dup in to_move:
            # Periodic lock check for dry-run mode
            if lock_checker:
                try:
                    lock_checker.periodic_check()
                except LockAcquisitionError as e:
                    print(f"\nERROR: {e}")
                    print("Aborting dry-run operation.")
                    session.close()
                    return 1

            source_path = Path(dup.path)

            # Check if source file exists
            if not source_path.exists():
                print(f"    SKIP: {dup.path} (id={dup.id}) - file not found")
                continue

            # Get the appropriate duplicate folder for this file's drive
            try:
                duplicate_dir = get_duplicate_folder_for_file(
                    source_path,
                    duplicate_folders,
                    legacy_duplicate_folder=config.get("duplicate_folder")
                )
            except ValueError as e:
                print(f"    ERROR: {e}")
                continue

            # Create duplicate folder if it doesn't exist (for dry-run case)
            if not duplicate_dir.exists() and not dry_run:
                try:
                    duplicate_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    print(f"    ERROR: Failed to create {duplicate_dir}: {e}")
                    continue

            # Generate unique target path
            target_path = get_unique_path(duplicate_dir, source_path.name)

            if dry_run:
                try:
                    print(f"    [DRY RUN] Would move: {source_path} -> {target_path}")
                except Exception:
                    print(f"    [DRY RUN] Would move: [path] -> {target_path}")
                total_moved += 1
                total_bytes_saved += dup.size
            else:
                try:
                    # Move the file
                    shutil.move(str(source_path), str(target_path))
                    try:
                        print(f"    Moved: {source_path} -> {target_path}")
                    except Exception:
                        print(f"    Moved: [path] -> {target_path}")

                    # Update database with new path AND name
                    dup.path = str(target_path.resolve())
                    dup.name = target_path.name  # FIX: Update name field with new filename
                    session.commit()

                    total_moved += 1
                    total_bytes_saved += dup.size

                except Exception as e:
                    print(f"    ERROR moving {source_path}: {e}")
                    session.rollback()

    # Summary
    print(f"\n{'='*80}")
    print("DEDUPLICATION SUMMARY")
    print(f"{'='*80}")
    if dry_run:
        print(f"  [DRY RUN] Would move: {total_moved} files")
    else:
        print(f"  Files moved: {total_moved}")
        print(f"  Disk space saved: {total_bytes_saved:,} bytes ({total_bytes_saved / (1024**2):.2f} MB)")
        print(f"  Duplicate folder: {duplicate_dir}")

    session.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move duplicate files to a designated folder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be moved
  python scripts/deduplicate.py --config config.json --dry-run

  # Actually move duplicates
  python scripts/deduplicate.py --config config.json

  # Only deduplicate files in specific folders
  python scripts/deduplicate.py --config config.json --folders "Z:\\MacMini\\20251007" "Z:\\MacMini\\20251010"
        """
    )

    parser.add_argument("--config", default="config.json", help="Path to JSON config file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without actually moving files")
    parser.add_argument("--folders", nargs="+", help="Optional: only process duplicates in these folders")

    args = parser.parse_args()

    # Resolve config path
    config_path = Path(args.config)
    if not config_path.exists():
        # Try CWD
        alt_path = Path.cwd() / args.config
        if alt_path.exists():
            config_path = alt_path
        else:
            print(f"ERROR: Config file not found: {args.config}")
            return 1

    return deduplicate_files(
        config_path=str(config_path),
        dry_run=args.dry_run,
        folders=args.folders
    )


if __name__ == "__main__":
    raise SystemExit(main())
