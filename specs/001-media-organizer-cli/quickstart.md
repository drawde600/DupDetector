# Quickstart: Media Organizer CLI

## Installation

1.  Clone the repository:
    ```bash
    git clone <repository_url>
    ```
2.  Install the dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

1.  Create a `config.json` file with the following content:
    ```json
    {
        "database": "media.db",
        "media_folders": [
            "/path/to/your/media"
        ],
        "duplicate_folder": "/path/to/your/duplicates",
        "exiftool_path": "C:\\Program Files\\exiftool-12.96_64\\exiftool.exe",
        "rename_format": "{MD5}-{related_id}-{PHASH}"
    }
    ```

## Usage

### Scan for media files

```bash
python main.py scan
```

### Find and move duplicates

```bash
python main.py duplicates --move-to /path/to/your/duplicates
```

### Reorganize files

```bash
python main.py reorganize /path/to/your/media /path/to/your/organized_media --by-date
```

### Tag a file

```bash
python main.py tag /path/to/your/media/file.jpg "vacation"
```
