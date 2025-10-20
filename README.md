# DupDetector

DupDetector is a small CLI to scan folders for media files, compute file hashes, and persist records to a database.

## Configuration

DupDetector reads scan options from a `config.json` file in the working directory by default. You can provide a custom config path using the `--config` flag to the `scan` command.

Example `config.json`:

```json
{
  "database": "mysql+pymysql://user:pass@localhost:3306/photodb",
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
  "extensions": ["jpg", "jpeg", "png", "gif", "heic", "mp4", "mov", "mkv"],
  "min_size": 1024,
  "max_size": 104857600
}
```

### Duplicate Folders

The `duplicate_folders` configuration maps drives to duplicate folder paths. This ensures duplicate files are never moved across drives during deduplication.

**Important:**
- Each drive must have a corresponding duplicate folder
- Duplicate folders must be absolute paths with drive letters
- Cross-drive moves are prevented automatically

See [docs/duplicate_folders.md](docs/duplicate_folders.md) for detailed configuration guide.

## Utilities

DupDetector includes several command-line utilities for different operations:

- **run_scan_persist.py** - Scan folders and persist to database
- **deduplicate.py** - Move duplicate files to duplicate folders
- **purge_duplicates.py** - Delete verified duplicates
- **scan_limited.py** - Test scanner with limited file count

**For complete documentation of all utilities and their options, see:**
### 📚 [**Utilities Reference**](docs/utilities.md)

### Quick Start

```powershell
# Initial scan
python scripts/run_scan_persist.py --config config.json

# Find and move duplicates
python scripts/deduplicate.py --config config.json --dry-run
python scripts/deduplicate.py --config config.json

# Purge verified duplicates
python scripts/purge_duplicates.py --config config.json --dry-run
python scripts/purge_duplicates.py --config config.json
```

## Development
See [`AGENTS.md`](AGENTS.md) for contributor guidelines.


Run tests with:

```powershell
python -m pytest -q
```

## Migrations

This project includes Alembic migration scripts under the `alembic/versions/` folder. To apply migrations locally you need to configure a database URL and run Alembic.

1. Install Alembic in your environment (if not already):

```powershell
pip install alembic
```

2. Configure the database URL. Edit `alembic.ini` or set the `sqlalchemy.url` key in the file, for example to use a local SQLite file:

```ini
[alembic]
script_location = alembic
sqlalchemy.url = sqlite:///./dupdetector.db
```

Alternatively, you can set the `DATABASE_URL` environment variable and modify `alembic/env.py` to read from it.

3. Run migrations:

```powershell
alembic upgrade head
```

This will apply all migrations (0001 -> 0002 -> 0003 -> 0004) and create the recommended indexes (md5_hash, photo_hash, duplicate_of_id, related_id).

Note about shells and examples
--------------------------------

This repository and its maintainer primarily use Windows PowerShell as the development
and runtime environment. All command examples in this README and other docs use
PowerShell syntax and paths. If you're contributing or asking for help, please use
PowerShell-style examples (backslashes in paths, PowerShell here-strings, etc.).

If you need Bash examples too, request them explicitly — the default is PowerShell.

# DupDetector
