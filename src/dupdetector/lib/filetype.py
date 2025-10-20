"""File type detection using magic bytes (file signatures).

This module detects actual file types by reading file content,
not relying on file extensions which can be incorrect or missing.
"""
from pathlib import Path
from typing import Optional
import magic


def detect_media_type(file_path: str) -> Optional[str]:
    """Detect the actual media type of a file using magic bytes.

    Args:
        file_path: Absolute path to the file

    Returns:
        Media type string (e.g., 'image/jpeg', 'video/mp4', 'image/png')
        or None if detection fails

    Examples:
        >>> detect_media_type('/path/to/photo.jpg')
        'image/jpeg'
        >>> detect_media_type('/path/to/wrong_extension.txt')  # actually a PNG
        'image/png'
    """
    try:
        mime = magic.Magic(mime=True)
        media_type = mime.from_file(file_path)
        return media_type
    except Exception:
        return None


def get_file_category(media_type: Optional[str]) -> Optional[str]:
    """Categorize a media type into broad categories.

    Args:
        media_type: MIME type string (e.g., 'image/jpeg')

    Returns:
        Category: 'image', 'video', 'audio', or None

    Examples:
        >>> get_file_category('image/jpeg')
        'image'
        >>> get_file_category('video/mp4')
        'video'
        >>> get_file_category('application/pdf')
        None
    """
    if not media_type:
        return None

    if media_type.startswith('image/'):
        return 'image'
    elif media_type.startswith('video/'):
        return 'video'
    elif media_type.startswith('audio/'):
        return 'audio'

    return None


def is_supported_media(media_type: Optional[str]) -> bool:
    """Check if a media type is supported for photo/video operations.

    Args:
        media_type: MIME type string

    Returns:
        True if the file is an image or video

    Examples:
        >>> is_supported_media('image/jpeg')
        True
        >>> is_supported_media('video/quicktime')
        True
        >>> is_supported_media('application/pdf')
        False
    """
    category = get_file_category(media_type)
    return category in ('image', 'video')


def get_human_readable_type(media_type: Optional[str]) -> str:
    """Convert MIME type to human-readable format.

    Args:
        media_type: MIME type string

    Returns:
        Human-readable type string

    Examples:
        >>> get_human_readable_type('image/jpeg')
        'JPEG Image'
        >>> get_human_readable_type('video/mp4')
        'MP4 Video'
        >>> get_human_readable_type('image/x-canon-cr2')
        'Canon RAW (CR2)'
    """
    if not media_type:
        return 'Unknown'

    # Map common MIME types to readable names
    type_map = {
        'image/jpeg': 'JPEG Image',
        'image/png': 'PNG Image',
        'image/gif': 'GIF Image',
        'image/bmp': 'BMP Image',
        'image/tiff': 'TIFF Image',
        'image/heic': 'HEIC Image',
        'image/heif': 'HEIF Image',
        'image/webp': 'WebP Image',
        'image/x-canon-cr2': 'Canon RAW (CR2)',
        'image/x-canon-cr3': 'Canon RAW (CR3)',
        'image/x-nikon-nef': 'Nikon RAW (NEF)',
        'image/x-sony-arw': 'Sony RAW (ARW)',
        'image/x-adobe-dng': 'Adobe DNG RAW',
        'video/mp4': 'MP4 Video',
        'video/quicktime': 'QuickTime Video',
        'video/x-matroska': 'Matroska Video (MKV)',
        'video/mpeg': 'MPEG Video',
        'video/x-msvideo': 'AVI Video',
        'video/x-ms-wmv': 'Windows Media Video',
    }

    return type_map.get(media_type, media_type)
