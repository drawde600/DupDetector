# DupDetector Utilities Reference

Complete reference for all command-line utilities and their options.

## Table of Contents

1. [Scanning](#scanning)
   - [run_scan_persist.py](#run_scan_persistpy)
   - [scan_limited.py](#scan_limitedpy)
2. [Deduplication](#deduplication)
   - [deduplicate.py](#deduplicatepy)
3. [Purging](#purging)
   - [purge_duplicates.py](#purge_duplicatespy)

---

## Scanning

### run_scan_persist.py

Main scanning utility for discovering media files, computing hashes, and persisting to database.

**Purpose**: Scan folders for media files, extract EXIF data, compute MD5 and perceptual hashes, and store results in database.

**Usage**:
```bash
python scripts/run_scan_persist.py --config config.json [OPTIONS]
```

**Options**:
- `--config PATH` (required) - Path to configuration file
- `--verbose` - Enable verbose output showing detailed progress
- `--workers N` - Number of parallel workers (overrides config)
- `--limit N` - Maximum number of files to scan

**Configuration** (config.json):
```json
{
  "database": "mysql+pymysql://user:pass@host:3306/dbname",
  "media_folders": ["Z:\\Photos", "C:\\Pictures"],
  "workers": 16,
  "recursive": true,
  "extensions": ["jpg", "jpeg", "png", "mp4", "mov"],
  "min_size": 1024,
  "max_size": null,
  "exiftool_path": "C:\\Program Files\\exiftool-12.96_64\\exiftool.exe"
}
```

**Example**:
```bash
# Scan with default verbosity
python scripts/run_scan_persist.py --config config.json

# Scan with verbose output
python scripts/run_scan_persist.py --config config.json --verbose

# Scan with custom worker count
python scripts/run_scan_persist.py --config config.json --workers 8

# Scan limited number of files (for testing)
python scripts/run_scan_persist.py --config config.json --limit 100
```

**Output**:
- File discovery progress (every 2 seconds)
- Preflight timing
- Batch processing progress
- Final statistics (files processed, duplicates found, errors)

**Important**:
- Acquires exclusive database lock to prevent concurrent scans
- Lock timeout: 4 hours (for large scans)
- Cannot run while deduplication or purge is active

---

### scan_limited.py

Limited scanning utility for testing purposes.

**Purpose**: Scan a limited number of files for testing scanner functionality.

**Usage**:
```bash
python scripts/scan_limited.py --config config.json --limit N
```

**Options**:
- `--config PATH` (required) - Path to configuration file
- `--limit N` (required) - Maximum number of files to scan

**Example**:
```bash
# Test scan with 50 files
python scripts/scan_limited.py --config config.json --limit 50
```

---

## Deduplication

### deduplicate.py

Move duplicate files to designated duplicate folders.

**Purpose**: Identify files with identical MD5 hashes and move duplicates to drive-specific duplicate folders, keeping the file with the lowest database ID.

**Usage**:
```bash
python scripts/deduplicate.py --config config.json [OPTIONS]
```

**Options**:
- `--config PATH` (required) - Path to configuration file
- `--dry-run` - Show what would be moved without actually moving files
- `--folders PATH [PATH ...]` - Limit deduplication to specific folders

**Configuration** (config.json):
```json
{
  "duplicate_folders": {
    "Z:\\": "Z:\\MacMini\\duplicates",
    "C:\\": "C:\\temp\\duplicates"
  }
}
```

**Important**:
- Files are NEVER moved across drives
- Each drive must have a corresponding duplicate folder
- Only one duplicate folder allowed per drive
- Keeps file with lowest ID (oldest scan)
- Updates database path and name fields
- **Database locking**:
  - Normal mode: Acquires exclusive lock (prevents all other operations)
  - Dry-run mode: Checks for locks periodically, aborts if lock acquired

**Example**:
```bash
# Dry run to see what would be moved
python scripts/deduplicate.py --config config.json --dry-run

# Actually move duplicates
python scripts/deduplicate.py --config config.json

# Deduplicate specific folders only
python scripts/deduplicate.py --config config.json --folders "Z:\\Photos\\2024"

# Deduplicate multiple folders
python scripts/deduplicate.py --config config.json --folders "Z:\\Photos" "C:\\Pictures"
```

**Output**:
```
Duplicate folder configuration loaded: 2 drive(s)
  Z:\ -> Z:\MacMini\duplicates
  C:\ -> C:\temp\duplicates

Finding duplicates...
Found 150 MD5 groups with duplicates

MD5: a1b2c3d4e5f6...
  Keeping: Z:\Photos\IMG_001.jpg (id=100, size=2048576)
  Moving 2 duplicate(s):
    Moved: Z:\Photos\Copy\IMG_001.jpg -> Z:\MacMini\duplicates\IMG_001-dup1.jpg

DEDUPLICATION SUMMARY
  Files moved: 250
  Disk space saved: 512,000,000 bytes (488.28 MB)
```

---

## Purging

### purge_duplicates.py

Purge utility for deleting verified duplicate files.

**Purpose**: Permanently delete files from duplicate folders after manual verification, marking them as deleted in the database. Uses batch database queries for optimal performance.

**Usage**:
```bash
python scripts/purge_duplicates.py --config config.json [OPTIONS]
```

**Options**:
- `--config PATH` (required) - Path to configuration file
- `--dry-run` - Show what would be purged without deleting
- `--pattern GLOB` - Glob pattern to filter files (e.g., `"*.jpg"`, `"*-dup*.jpg"`)
- `--older-than-days N` - Only purge files older than N days
- `--drive DRIVE` - Only purge files on specific drive (e.g., `"Z:"` or `"Z"`)

**Important**:
- **PERMANENTLY DELETES FILES** - use `--dry-run` first
- Only processes files that exist in database
- **Orphaned files** (on disk but not in DB) are SKIPPED - must be deleted manually
- Requires typing "DELETE" to confirm (unless dry-run)
- **Database locking**:
  - Normal mode: Acquires exclusive lock (prevents all other operations)
  - Dry-run mode: Checks for locks periodically, aborts if lock acquired

**Example**:
```bash
# Dry run to see what would be purged
python scripts/purge_duplicates.py --config config.json --dry-run

# Purge all verified duplicates
python scripts/purge_duplicates.py --config config.json

# Purge only JPEG files
python scripts/purge_duplicates.py --config config.json --pattern "*.jpg"

# Purge only files with -dup suffix
python scripts/purge_duplicates.py --config config.json --pattern "*-dup*.*"

# Purge files older than 30 days
python scripts/purge_duplicates.py --config config.json --older-than-days 30

# Purge only files on Z: drive
python scripts/purge_duplicates.py --config config.json --drive Z:

# Combine filters
python scripts/purge_duplicates.py --config config.json --drive Z: --pattern "*.jpg" --older-than-days 7
```

**Output**:
```
Acquiring database lock...
Database lock acquired for purge operation

Scanning duplicate folders...
  Scanning: Z:\MacMini\duplicates
    Found 5234 file(s)
  Total files found: 5234

BUILDING PURGE PLAN
Checking 5234 files against database...
  Checked 5234/5234 files checked
  Result: 5230 in DB, 4 orphaned (will be skipped)

Files to purge:
  In database:     5230
  Not in database: 4 (will be skipped - delete manually)
  Total to purge:  5230
  Total size:      2,147,483,648 bytes (2048.00 MB)

Note: 4 orphaned files found (not in database).
These will NOT be purged by this script. Delete manually if needed.

WARNING: This will PERMANENTLY DELETE files!
================================================================================

Type 'DELETE' to confirm purge: DELETE

PURGING FILES
================================================================================
  1/5230 Purged: IMG_8559-dup1.JPG (id=18614)
  2/5230 Purged: IMG_8560-dup1.JPG (id=18615)
  ...
  5230/5230 Purged: IMG_9999-dup1.JPG (id=23843)

PURGE SUMMARY
================================================================================
  Files deleted: 5230
  Database records marked deleted: 5230
  Errors: 0
  Disk space freed: 2,147,483,648 bytes (2048.00 MB)
  Orphaned files skipped: 4 (delete manually)
```

---

## Common Workflows

### Initial Setup

1. Create config.json with database and media folder settings
2. Run migration: `alembic upgrade head`
3. Run initial scan: `python scripts/run_scan_persist.py --config config.json`

### Regular Deduplication

1. Scan for new files: `python scripts/run_scan_persist.py --config config.json`
2. Dry-run deduplicate: `python scripts/deduplicate.py --config config.json --dry-run`
3. Review output and confirm duplicates are correct
4. Run deduplication: `python scripts/deduplicate.py --config config.json`
5. Manually verify files in duplicate folders
6. Purge verified duplicates: `python scripts/purge_duplicates.py --config config.json`

### Targeted Purge

1. Purge specific drive: `python scripts/purge_duplicates.py --config config.json --drive Z:`
2. Purge specific file types: `python scripts/purge_duplicates.py --config config.json --pattern "*.jpg"`
3. Purge old files only: `python scripts/purge_duplicates.py --config config.json --older-than-days 30`

### Testing/Development

1. Test scan: `python scripts/scan_limited.py --config config.json --limit 50`
2. Test deduplicate: `python scripts/deduplicate.py --config config.json --dry-run`
3. Test purge: `python scripts/purge_duplicates.py --config config.json --dry-run`

---

## Safety Features

### Database Locking

All operations use database-level locks to prevent conflicts:

**Normal Operations** (acquire exclusive lock):
- **run_scan_persist.py**: Acquires `scan` lock (4 hour timeout)
- **deduplicate.py**: Acquires `deduplicate` lock (2 hour timeout)
- **purge_duplicates.py**: Acquires `purge` lock (2 hour timeout)

**Dry-Run Operations** (check locks periodically):
- **Does NOT acquire locks** (read-only mode)
- Checks if lock exists at startup (fails if operation is running)
- Periodically checks every 60 seconds during execution
- Aborts if another process acquires lock during dry-run

**Parallel Execution**:
- ✅ Multiple dry-runs can run in parallel (no locks acquired)
- ❌ Cannot run dry-run if normal operation is active
- ❌ Cannot run normal operation if dry-run is active (will abort dry-run)

Example errors:
```
# Starting dry-run while normal operation is running:
ERROR: Lock 'purge' is currently held by PID 12345 on COMPUTER1 (acquired at 2025-10-20 14:30:00).
Cannot run dry-run while operation is active.

# Normal operation starting during dry-run:
ERROR: Lock 'purge' was acquired by PID 12345 on COMPUTER1 during dry-run. Aborting dry-run operation.
```

### Cross-Drive Protection

Deduplication never moves files across drives:
```
ERROR: Duplicate folder Z:\MacMini\duplicates is on drive Z:,
       but file C:\photos\image.jpg is on drive C:.
       Cross-drive moves are not allowed.
```

### Orphaned File Handling

Purge scripts skip files without database entries:
```
Note: 42 orphaned files found (not in database).
These will NOT be purged by this script. Delete manually if needed.
```

### Dry-Run Mode

All destructive operations support `--dry-run` to preview changes without applying them.

---

## Configuration Reference

See [duplicate_folders.md](duplicate_folders.md) for detailed duplicate folder configuration.

### Essential Settings

```json
{
  "database": "mysql+pymysql://user:pass@localhost:3306/photodb",
  "geodatabase": "mysql+pymysql://user:pass@localhost:3306/geonames",
  "media_folders": [
    "Z:\\MacMini\\photos",
    "C:\\Users\\Public\\Pictures"
  ],
  "duplicate_folders": {
    "Z:\\": "Z:\\MacMini\\duplicates",
    "C:\\": "C:\\temp\\duplicates"
  },
  "workers": 16,
  "recursive": true,
  "extensions": ["jpg", "jpeg", "png", "bmp", "dng", "cr2", "cr3", "gif", "heic", "mp4", "mov", "mkv", "mpg", "mpeg", "avi"],
  "min_size": null,
  "max_size": null,
  "exiftool_path": "C:\\Program Files\\exiftool-12.96_64\\exiftool.exe"
}
```

### Settings Explanation

- `database` - Main database connection string (MySQL or SQLite)
- `geodatabase` - Optional geonames database for location tagging
- `media_folders` - List of folders to scan (absolute paths with drive letters)
- `duplicate_folders` - Map of drive letters to duplicate folder paths
- `workers` - Number of parallel workers for scanning (default: 16)
- `recursive` - Scan subdirectories (default: true)
- `extensions` - File extensions to scan (case-insensitive)
- `min_size` - Minimum file size in bytes (null = no minimum)
- `max_size` - Maximum file size in bytes (null = no maximum)
- `exiftool_path` - Path to exiftool executable for EXIF extraction
