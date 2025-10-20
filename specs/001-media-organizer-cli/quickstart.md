# Quickstart: Media Organizer CLI

## Installation

1.  Clone the repository:
    ```powershell
    git clone <repository_url>
    ```
2.  Install the dependencies:
    ```powershell
    pip install -r requirements.txt
    ```

## Configuration

1.  Create a `config.json` file with the following content. Note: `geodatabase` is REQUIRED for reverse-geocoding during scans.
    ```json
    {
        "database": "media.db",
        "media_folders": [
            "C:\path\to\your\media"
        ],
        "duplicate_folder": "C:\path\to\your\duplicates",
        "exiftool_path": "C:\Program Files\exiftool-12.96_64\exiftool.exe",
        "geodatabase": "mysql+pymysql://user:pass@host:3306/geonames",
        "rename_format": "{MD5}-{related_id}-{PHASH}"
    }
    ```

Important notes:

- EXIF extraction is mandatory for scans. Ensure `exiftool_path` points to a working exiftool binary.
- Reverse-geocoding uses the local GeoNames DB given by `geodatabase`. If a file's EXIF contains GPS coordinates but the geodatabase lookup cannot resolve both `city` and `country`, the scan will abort (fail-fast) to avoid inserting incomplete geo-derived data.

## Usage

### Scan for media files

```powershell
dupdetector scan C:\path\to\your\media
```

### Find and move duplicates

```powershell
dupdetector duplicates --move-to C:\path\to\your\duplicates
```

### Reorganize files

```powershell
dupdetector reorganize C:\path\to\your\media C:\path\to\your\organized_media --by-date
```

### Tag a file

```powershell
dupdetector tag C:\path\to\your\media\file.jpg "vacation"
```
