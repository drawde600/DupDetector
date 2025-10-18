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
# DupDetector