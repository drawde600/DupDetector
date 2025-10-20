"""Duplicate folder configuration and path resolution.

This module handles the mapping between media folders and their corresponding
duplicate folders, ensuring files are never moved across drives.

Configuration format:
{
    "duplicate_folders": {
        "Z:\\": "Z:\\MacMini\\duplicates",
        "C:\\": "C:\\temp\\duplicates"
    }
}

Or legacy format (still supported):
{
    "duplicate_folder": "Z:\\MacMini\\duplicates"
}
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def get_drive_letter(path: str | Path) -> str:
    """Extract drive letter from a Windows path.

    Args:
        path: File or folder path

    Returns:
        Drive letter with colon (e.g., "Z:")

    Raises:
        ValueError: If path doesn't contain a drive letter
    """
    path_str = str(path)

    # Handle UNC paths
    if path_str.startswith("\\\\"):
        raise ValueError(f"UNC paths are not supported: {path_str}")

    # Extract drive letter
    if len(path_str) >= 2 and path_str[1] == ':':
        return path_str[0:2].upper()

    raise ValueError(f"Path does not contain a drive letter: {path_str}")


def get_duplicate_folder_for_file(
    file_path: str | Path,
    duplicate_folders: dict[str, str],
    legacy_duplicate_folder: Optional[str] = None
) -> Path:
    """Get the duplicate folder path for a given file.

    This function ensures files are never moved across drives by matching
    the file's drive to the appropriate duplicate folder.

    Args:
        file_path: Path to the file being moved
        duplicate_folders: Dict mapping drive roots to duplicate folders
                          e.g., {"Z:\\": "Z:\\MacMini\\duplicates"}
        legacy_duplicate_folder: Fallback duplicate_folder from old config format

    Returns:
        Path to the duplicate folder on the same drive as the file

    Raises:
        ValueError: If no duplicate folder is configured for the file's drive
    """
    file_path_obj = Path(file_path).resolve()

    # Get the file's drive
    try:
        file_drive = get_drive_letter(file_path_obj)
    except ValueError as e:
        raise ValueError(f"Cannot determine drive for file: {file_path}") from e

    # Try to find matching duplicate folder
    # First check with backslash (Z:\)
    drive_with_backslash = file_drive + "\\"

    if drive_with_backslash in duplicate_folders:
        dup_folder = duplicate_folders[drive_with_backslash]
    elif file_drive in duplicate_folders:
        # Also check without backslash (Z:)
        dup_folder = duplicate_folders[file_drive]
    elif legacy_duplicate_folder:
        # Fall back to legacy single duplicate_folder
        dup_folder = legacy_duplicate_folder
    else:
        raise ValueError(
            f"No duplicate folder configured for drive {file_drive}. "
            f"Available drives: {list(duplicate_folders.keys())}"
        )

    dup_folder_path = Path(dup_folder).resolve()

    # Verify the duplicate folder is on the same drive
    try:
        dup_drive = get_drive_letter(dup_folder_path)
    except ValueError as e:
        raise ValueError(f"Invalid duplicate folder path: {dup_folder}") from e

    if dup_drive != file_drive:
        raise ValueError(
            f"Duplicate folder {dup_folder} is on drive {dup_drive}, "
            f"but file {file_path} is on drive {file_drive}. "
            f"Cross-drive moves are not allowed."
        )

    return dup_folder_path


def validate_duplicate_folders_config(
    duplicate_folders: dict[str, str],
    media_folders: list[str]
) -> list[str]:
    """Validate duplicate_folders configuration.

    Args:
        duplicate_folders: Dict mapping drive roots to duplicate folders
        media_folders: List of media folder paths to check coverage

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Check that all duplicate folder paths are absolute with drive letters
    for drive_key, dup_folder in duplicate_folders.items():
        dup_path = Path(dup_folder)

        # Check if path is absolute
        if not dup_path.is_absolute():
            errors.append(
                f"Duplicate folder must be absolute path: {dup_folder}"
            )
            continue

        # Check if path has drive letter
        try:
            dup_drive = get_drive_letter(dup_folder)
        except ValueError:
            errors.append(
                f"Duplicate folder must include drive letter: {dup_folder}"
            )
            continue

        # Check that the drive key matches the duplicate folder's drive
        drive_key_clean = drive_key.rstrip("\\")
        if drive_key_clean != dup_drive:
            errors.append(
                f"Drive key '{drive_key}' does not match duplicate folder drive '{dup_drive}': {dup_folder}"
            )

    # Check that all media folders have a matching duplicate folder
    for media_folder in media_folders:
        try:
            media_drive = get_drive_letter(media_folder)
            drive_with_backslash = media_drive + "\\"

            if drive_with_backslash not in duplicate_folders and media_drive not in duplicate_folders:
                errors.append(
                    f"No duplicate folder configured for media folder drive {media_drive}: {media_folder}"
                )
        except ValueError as e:
            errors.append(f"Invalid media folder path: {media_folder} ({e})")

    return errors


def load_duplicate_folders_from_config(config: dict) -> dict[str, str]:
    """Load duplicate folders configuration from config dict.

    Supports both new format (duplicate_folders) and legacy format (duplicate_folder).

    Args:
        config: Configuration dictionary

    Returns:
        Dict mapping drive roots to duplicate folders

    Raises:
        ValueError: If configuration is invalid
    """
    # Check for new format first
    if "duplicate_folders" in config:
        dup_folders = config["duplicate_folders"]

        if not isinstance(dup_folders, dict):
            raise ValueError(
                "duplicate_folders must be a dict mapping drives to folder paths"
            )

        # Validate: ensure only one duplicate folder per drive
        # Normalize all drive keys and check for duplicates
        normalized_drives = {}
        for drive_key, folder_path in dup_folders.items():
            # Normalize drive key (remove trailing backslash if present)
            normalized_key = drive_key.rstrip("\\")

            if normalized_key in normalized_drives:
                raise ValueError(
                    f"Duplicate configuration for drive {normalized_key}: "
                    f"'{normalized_drives[normalized_key]}' and '{folder_path}'. "
                    f"Only one duplicate folder allowed per drive."
                )

            normalized_drives[normalized_key] = folder_path

        # Return with standardized keys (with backslash)
        return {f"{drive}\\": path for drive, path in normalized_drives.items()}

    # Fall back to legacy format
    elif "duplicate_folder" in config:
        legacy_folder = config["duplicate_folder"]

        if not legacy_folder:
            raise ValueError("duplicate_folder is empty")

        # Extract drive from legacy folder and create mapping
        try:
            drive = get_drive_letter(legacy_folder)
            drive_with_backslash = drive + "\\"
            return {drive_with_backslash: legacy_folder}
        except ValueError as e:
            raise ValueError(f"Invalid duplicate_folder path: {legacy_folder}") from e

    else:
        raise ValueError(
            "Configuration must include either 'duplicate_folders' or 'duplicate_folder'"
        )
