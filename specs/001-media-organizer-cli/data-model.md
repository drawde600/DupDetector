# Data Model

This document describes the data model for the Media Organizer CLI.

## Entities

### File

Represents a media file in the system.

| Attribute | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `related_id` | Integer | An ID to group related files. |
| `previous_version_id` | Integer | A self-referencing foreign key to link to the previous version of the file record. |
| `name` | String | The name of the file. |
| `original_name` | String | The original name of the file. |
| `path` | String | The absolute path to the file. |
| `original_path` | String | The original path of the file. |
| `size` | Integer | The size of the file in bytes. |
| `md5_hash` | String | The MD5 hash of the file content. |
| `perceptual_hash` | String | The perceptual hash of the image. |
| `status` | String | The status of the file. Can be `new`, `scanned`, `duplicate`, `deleted`. |
| `dimensions` | String | The dimensions of the media (e.g., "1920x1080"). |
| `manufacturer` | String | The manufacturer of the camera/device from EXIF. |
| `content_identifier` | String | An identifier to group related assets from the same device (e.g., for iPhone Live Photos). |
| `created_at` | DateTime | The timestamp when the file was first added to the database. |
| `updated_at` | DateTime | The timestamp when the file record was last updated. |
| `taken_at` | DateTime | The timestamp when the photo or video was taken (from EXIF). |
| `gps_latitude` | Float | The GPS latitude from EXIF. |
| `gps_longitude` | Float | The GPS longitude from EXIF. |
| `gps_city` | String | The city from reverse geocoding. |
| `gps_country` | String | The country from reverse geocoding. |

### Tag

Represents a custom tag that can be applied to a file.

| Attribute | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `name` | String | The name of the tag (e.g., "vacation", "family"). |

### FileTag (Association Table)

Represents the many-to-many relationship between `File` and `Tag`.

| Attribute | Type | Description |
|---|---|---|
| `file_id` | Integer | Foreign key to the `File` table. |
| `tag_id` | Integer | Foreign key to the `Tag` table. |

### ExifData

Represents the raw EXIF data for a file.

**Note**: For any given file, the `id` of its `ExifData` record and the `file_id` foreign key will both have the same value as the `id` of the `File` record, creating a parallel ID structure.

| Attribute | Type | Description |
|---|---|---|
| `id` | Integer | Primary key. |
| `file_id` | Integer | Foreign key to the `File` table. |
| `raw_data` | JSON | The raw EXIF data as a JSON object. |