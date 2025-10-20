# Duplicate Folders Configuration

## Overview

The `duplicate_folders` configuration maps each drive to a specific duplicate folder. This ensures that duplicate files are never moved across drives, which would be slow and potentially problematic.

## Configuration Format

### New Format (Recommended)

```json
{
  "duplicate_folders": {
    "Z:\\": "Z:\\MacMini\\duplicates",
    "C:\\": "C:\\temp\\duplicates"
  }
}
```

**Key points:**
- Keys are drive roots with backslash (e.g., `"Z:\\"`)
- Values are full absolute paths to duplicate folders
- Each duplicate folder MUST be on the same drive as specified in the key
- All paths must include drive letters

### Legacy Format (Still Supported)

```json
{
  "duplicate_folder": "Z:\\MacMini\\duplicates"
}
```

The legacy single `duplicate_folder` format is still supported for backward compatibility. It will be automatically converted to use the drive of the specified folder.

## How It Works

### Deduplication (`scripts/deduplicate.py`)

When moving duplicate files:

1. The script loads the `duplicate_folders` configuration
2. For each duplicate file to be moved:
   - Extracts the file's drive letter (e.g., `Z:`)
   - Looks up the corresponding duplicate folder for that drive
   - Moves the file to that drive's duplicate folder
   - **Never moves files across drives**

3. If no duplicate folder is configured for a file's drive, the operation fails with an error

### Purging (`scripts/purge_duplicates.py`)

When purging verified duplicates:

1. The script loads the `duplicate_folders` configuration
2. Scans ALL configured duplicate folders for files
3. Only processes files that exist in the database
4. **Skips orphaned files** (files on disk but not in database) - these must be deleted manually

## Validation

The configuration is validated when loading:

1. **Absolute paths**: All duplicate folder paths must be absolute with drive letters
2. **Drive matching**: Each duplicate folder must be on the same drive as its key
3. **Media folder coverage**: Every media folder's drive must have a corresponding duplicate folder

Example validation errors:

```
ERROR: Duplicate folder configuration validation failed:
  - Duplicate folder must be absolute path: duplicates
  - Drive key 'Z:\' does not match duplicate folder drive 'C:': C:\temp\dup
  - No duplicate folder configured for media folder drive Z:: Z:\MacMini\photos
```

## Migration Guide

### From Legacy to New Format

If you have:

```json
{
  "duplicate_folder": "Z:\\MacMini\\duplicates"
}
```

And your media folders span multiple drives:

```json
{
  "media_folders": [
    "Z:\\MacMini\\photos",
    "C:\\Users\\Public\\Pictures"
  ]
}
```

Update to:

```json
{
  "duplicate_folders": {
    "Z:\\": "Z:\\MacMini\\duplicates",
    "C:\\": "C:\\temp\\duplicates"
  }
}
```

### Creating Duplicate Folders

Make sure to create the duplicate folders before running deduplication:

```bash
# Windows Command Prompt
mkdir "Z:\MacMini\duplicates"
mkdir "C:\temp\duplicates"

# PowerShell
New-Item -Path "Z:\MacMini\duplicates" -ItemType Directory
New-Item -Path "C:\temp\duplicates" -ItemType Directory
```

Or let the deduplication script create them automatically (non-dry-run mode).

## Best Practices

1. **Same drive organization**: Keep duplicate folders on the same drive as their corresponding media folders
2. **Dedicated folders**: Use dedicated folders for duplicates (not nested inside media folders)
3. **Consistent naming**: Use consistent naming across drives (e.g., `duplicates` folder on each drive)
4. **Regular purging**: Periodically review and purge duplicate folders after verification

## Examples

### Single Drive Setup

```json
{
  "media_folders": ["Z:\\MacMini\\photos"],
  "duplicate_folders": {
    "Z:\\": "Z:\\MacMini\\duplicates"
  }
}
```

### Multi-Drive Setup

```json
{
  "media_folders": [
    "Z:\\MacMini\\photos",
    "Z:\\MacMini\\videos",
    "C:\\Users\\Public\\Pictures",
    "D:\\Archive\\media"
  ],
  "duplicate_folders": {
    "Z:\\": "Z:\\MacMini\\duplicates",
    "C:\\": "C:\\temp\\duplicates",
    "D:\\": "D:\\Archive\\duplicates"
  }
}
```

### Network Drive (Not Recommended)

UNC paths are not supported. Map network drives to drive letters first:

```
# Not supported:
"\\\\server\\share\\duplicates"

# Map to drive letter first:
net use X: \\server\share

# Then use:
{
  "duplicate_folders": {
    "X:\\": "X:\\duplicates"
  }
}
```

## Error Handling

### Cross-Drive Move Attempt

```
ERROR: Duplicate folder Z:\MacMini\duplicates is on drive Z:,
       but file C:\photos\image.jpg is on drive C:.
       Cross-drive moves are not allowed.
```

**Solution**: Configure a duplicate folder for drive C:

### Missing Drive Configuration

```
ERROR: No duplicate folder configured for drive C:.
       Available drives: ['Z:\']
```

**Solution**: Add drive C: to duplicate_folders configuration

### Orphaned Files

```
Note: 42 orphaned files found (not in database).
These will NOT be purged by this script. Delete manually if needed.
```

**Solution**: These are files in the duplicate folder that have no database entries. Review and delete manually if they are truly unwanted.
