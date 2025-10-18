# DupDetector

DupDetector is a small CLI to scan folders for media files, compute file hashes, and persist records to a database.

## Configuration

DupDetector reads scan options from a `config.json` file in the working directory by default. You can provide a custom config path using the `--config` flag to the `scan` command.

Example `config.json` (also provided as `config.example.json`):

```json
{
  "recursive": true,
  "extensions": ["jpg", "jpeg", "png", "gif", "heic", "mp4", "mov", "mkv"],
  "min_size": 1024,
  "max_size": 104857600
}
```

### Running the scanner

Run scan using the default `config.json`:

```powershell
python -m dupdetector.cli scan C:\path\to\media
```

Or specify a custom config path:

```powershell
python -m dupdetector.cli scan C:\path\to\media --config C:\path\to\config.json
```

## Development

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

# DupDetector