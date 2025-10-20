# Feature Specification: Media Organizer CLI

**Feature Branch**: `001-media-organizer-cli`  
**Created**: 2025-10-18  
**Status**: Draft  
**Input**: User description: "Build a command application that can help me organize my media files (photos and videos) check all the folders. Determine if there are duplicates (using md5) or related (some means to detect associated, date/time taken, metadata of apple content identifier, similarity of photo (perceptual hash). Store in database to minimize re-calculation, database can be re-fresh/recalculated might be due to new algo. Allow special Folder to dump duplicate, duplicates also marked in db as field. Original name stored in db. Allow to reorganize to flat mode, by date (multi-level : year only, year-month, year-month-day), by location, by custom tag. The configuration of the application is stored as json (config.json). Tagging can be done per file,files or directory. CRUD operations for tagging, there might be more than 1 tags per file. identical (md5 similar) files are expected to have same set of tags."

## Clarifications

### Session 2025-10-18

- Q: What should happen to the database entry when a file is moved or deleted outside of the application? → A: The user is responsible for manually updating the database when files are moved or deleted.
- Q: How should the application handle errors, such as when a file cannot be read or a folder cannot be accessed? → A: The application should display a user-friendly error message and log the detailed error information to a file.
- Q: What level of logging should be implemented? → A: Basic logging of major events and errors.
- Q: Should the application support importing or exporting data (e.g., the database or a list of duplicates)? → A: Yes, the application should support exporting data (e.g., a list of duplicates, tags) to a common format like CSV or JSON.
- Q: What features are explicitly out of scope for this version of the application? → A: Real-time file system monitoring, cloud storage integration, and advanced image editing capabilities are out of scope.
- Q: How should the application handle database entries for physically deleted files? → A: Add a `is_deleted` flag to the `File` table to mark entries as deleted.
- Q: Should the `File` table have separate columns for each metadata attribute, or should all additional metadata be stored in a single `metadata` column (e.g., as a JSON object)? → A: Use separate columns for each metadata attribute.
- Q: Which testing policy should we follow? → A: Automated-tests-required (tests may be authored in the same PR).

### Session 2025-10-19

- Q: How should the system track a file's state? → A: Single status field: Use a single `status` text field (e.g., `new`, `scanned`, `duplicate`, `deleted`).
- Q: How should error messages be presented to the user? → A: Structured: Include an error code and brief description, e.g., "Error E012: Failed to read file. See log for details."
- Q: What security measures should be implemented? → A: None: Assume the user runs the tool in a trusted environment.
- Q: What level of logging should be implemented? → A: Basic: Log only the start and end of major operations (like a scan) and any errors that occur.
- Q: What accessibility measures should be implemented? → A: None: No specific accessibility features will be implemented.
- Q: How should the application report progress during long operations? → A: It should print the index of the current file being processed and the total number of files (e.g., '50/100').
- Q: Which term should be used for the perceptual hash? → A: `perceptual_hash`.

### 2025-10-19 Update: EXIF & Geocoding behaviour

- EXIF extraction is mandatory during the initial scan. The CLI will run ExifTool (configured via `exiftool_path`) for every file scanned and will supply the raw JSON output into the repository layer.
- Derived fields (gps, city, country, taken_at, dimensions, manufacturer, etc.) MUST be applied to the `File` model prior to the database INSERT. A single atomic insert should populate these derived columns; the system will not perform a separate update after insert for initial scan rows.
- Reverse-geocoding uses a mandatory local GeoNames database specified by a `geodatabase` URL in `config.json` (example: `"geodatabase": "mysql+pymysql://user:pass@host:3306/geonames"`). The application will query this local DB and take the nearest match.
- There is no automatic backfill or large-scale post-hoc geocoding of historical rows. Geocoding happens inline during the initial scan and must succeed when GPS is present.
- Strict fail-fast policy: The scan will abort if the GeoNames database is unavailable or if the geocoding logic fails to resolve a city and country from existing GPS coordinates. This prevents the insertion of incomplete geo-derived data.
- The previous `GeocodeCache` model and separate caching/backfill scripts have been removed from the codebase; the spec documents this removal and the new single-provider requirement.

**Validation (2025-10-19)**: A quick import sanity check was run with `PYTHONPATH=src` and confirmed the updated modules import successfully: `dupdetector.services.repository` and `dupdetector.cli` both imported without error.

### Startup preflight checks (new)

The runner and CLI must perform a strict startup preflight before scanning. These checks are applied once at startup (not per-file) and must be documented and tested.

- Config load: load the effective config at startup using this precedence: (1) CLI `--config` if provided; (2) CWD `config.json` in the target folder; (3) package `src/dupdetector/config.json`.
- If the selected config cannot be parsed as JSON, abort startup and report the JSON error and path.

- ExifTool: if `exiftool_path` exists in the effective config, the runner must verify the file exists and is executable. If missing, abort startup with an actionable error (non-zero exit).

- Geodatabase (strict):
	- If the config contains a top-level `geodatabase` URL OR if `geocode.enabled` is true and `local_geonames` is configured, the runner must verify that the configured geodatabase is reachable before scanning.
	- The reachability check is a short (5s) attempt using the appropriate DB driver. If the geodatabase cannot be reached, abort the run and show a diagnostic message explaining common causes (bad creds, grants, host/port).

- Main database (non-strict):
	- The runner may attempt a short diagnostic connection to the `database` URL, but failure is non-fatal; on failure the runner should fall back to `sqlite:///dupdetector.db` and continue, logging the fallback.

- Quick candidate check: after preflight, perform a lightweight candidate file count using the effective `extensions`, `min_size`, `max_size`, and `recursive` settings and print the count. This is only diagnostic and not fatal.

Rationale: geocoding is a mandatory inline dependency of the scan (per project policy). Doing these checks once at startup avoids noisy per-file config prints and provides fast, actionable feedback to the user when required infrastructure is missing.

### Configuration Keys (Reference)

The following configuration keys must be documented in `config.json`:

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `database` | String (URL) | No | `sqlite:///dupdetector.db` | Main database connection URL |
| `geodatabase` | String (URL) | Yes (if geocoding enabled) | None | GeoNames database URL for reverse geocoding |
| `exiftool_path` | String (path) | Yes | None | Absolute path to `exiftool.exe` executable |
| `extensions` | List[String] | No | `[".jpg", ".jpeg", ".png", ".mp4", ".mov"]` | File extensions to scan |
| `min_size` | Integer (bytes) | No | `0` | Minimum file size to scan |
| `max_size` | Integer (bytes) | No | `null` (unlimited) | Maximum file size to scan |
| `recursive` | Boolean | No | `true` | Scan subdirectories recursively |
| `related_time_threshold_minutes` | Integer | No | `60` | Max time difference (minutes) for auto-clustering related files by GPS+time |
| `rename_format` | String | No | `"{YYYY}{MM}{DD}_{HH}{mm}{SS}_{MD5}{NN}"` | Template for file renaming (see FR-012 for placeholders) |
| `duplicate_folder` | String (path) | No | `./duplicates` | Destination folder for moved duplicates |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Duplicate Detection (Priority: P1)

As a user, I want to be able to scan my media folders and identify duplicate files so that I can free up storage space.

**Why this priority**: This is the core functionality of the application and provides the most immediate value to the user.

**Independent Test**: The user can run the application on a folder with known duplicate files and verify that the duplicates are correctly identified.

**Acceptance Scenarios**:

1. **Given** a folder with duplicate image and video files, **When** the user runs the duplicate detection command, **Then** the application should identify and report the duplicate files.
2. **Given** a folder with no duplicate files, **When** the user runs the duplicate detection command, **Then** the application should report that no duplicates were found.

---

### User Story 2 - File Reorganization (Priority: P2)

As a user, I want to be able to reorganize my media files into a new folder structure based on date, location, or custom tags, and to collate duplicates for manual verification.

**Why this priority**: This feature provides a powerful way for users to organize their media library and manage duplicates.

**Independent Test**: The user can run the reorganization command on a folder of media files and verify that the files are moved to the correct new folder structure and that duplicates are collated.

**Acceptance Scenarios**:

1. **Given** a folder of media files, **When** the user runs the reorganization command with the `by-date` option, **Then** the files should be moved to a new folder structure organized by year, month, and day.
2. **Given** a folder of media files, **When** the user runs the reorganization command with the `by-location` option, **Then** the files should be moved to a new folder structure organized by location.
3. **Given** a folder with duplicate files, **When** the user runs the reorganization command with the `--collate-duplicates` option, **Then** the extra duplicate files should be moved to a pre-defined folder for manual verification.

---

### User Story 3 - Tagging (Priority: P3)

As a user, I want to be able to add, remove, and view tags for my media files.

**Why this priority**: Tagging provides a flexible way for users to categorize and search for their media files.

**Independent Test**: The user can add, remove, and view tags for a media file and verify that the tags are correctly applied.

**Acceptance Scenarios**:

1. **Given** a media file, **When** the user runs the `tag` command with a new tag, **Then** the tag should be added to the file.
2. **Given** a media file with a tag, **When** the user runs the `untag` command with the tag, **Then** the tag should be removed from the file.

---

### User Story 4 - File Renaming (Priority: P4)

As a user, I want to be able to rename my media files based on a predefined format in the configuration file, including options to specify the source of date information (e.g., Exif, manual, file creation time).

**Why this priority**: This feature provides a way for users to have consistent naming for their media files.

**Independent Test**: The user can run the reorganization command with the `--rename` option and verify that the files are renamed according to the specified format and date source.

**Acceptance Scenarios**:

2. **Given** a folder of media files and a renaming format in the configuration file, **When** the user runs the reorganization command with the `--rename` option and a filename conflict occurs, **Then** the system should append a unique identifier to the subsequent files to prevent data loss.

---

### User Story 5 - Related ID Management (Priority: P5)

As a user, I want to be able to assign a related ID to my media files so that I can group related files together.

**Why this priority**: This feature provides a way for users to group related files that are not necessarily duplicates.

**Independent Test**: The user can add, remove, and view a related ID for a media file and verify that the related ID is correctly applied.

**Acceptance Scenarios**:

1. **Given** a new image is added to the database, **Then** a unique, auto-incremented `related_id` should be assigned to it.
2. **Given** a set of images, **When** the user runs the `related-id` command with a `related_id` and a set of image paths, **Then** the `related_id` should be assigned to all the images in the set.
3. **Given** a set of images with the same `related_id`, **When** the user runs the `related-id` command with a new `related_id` and the path to the latest image in the set, **Then** the `related_id` of the latest image should be updated.
4. **Given** an image is added to the database that has the same MD5 hash as an existing image, **Then** the new image should be assigned the same `related_id` as the existing image.

---

### User Story 6 - Post-Scan GPS Updates (Priority: P6)

As a user, I want to be able to add or update GPS information for my media files after the initial scan, so that I can correct or add location data.

**Why this priority**: This feature allows for greater flexibility and data accuracy, especially when dealing with files that have missing or incorrect GPS metadata.

**Independent Test**: The user can use a command-line utility to add or update the GPS coordinates for a file and verify that the new location data is correctly stored in the database, including the `geocode_provenance`.

**Acceptance Scenarios**:

1. **Given** a file with no GPS information, **When** the user runs the GPS update command with new coordinates, **Then** the system should update the file's record with the new GPS data, resolve the city and country, and set the `geocode_provenance` to `manual`.
2. **Given** a file with incorrect GPS information, **When** the user runs the GPS update command with corrected coordinates, **Then** the system should update the file's record with the new GPS data and update the `geocode_provenance`.

---

### User Story 7 - Rescan and Update (Priority: P7)

As a user, I want to be able to rescan my media library to detect changes, including edits, moves, and renames, so that my database stays up-to-date.

**Why this priority**: This feature is crucial for the long-term management of a media library, ensuring that the database accurately reflects the state of the file system.

**Independent Test**: The user can run the `update` command on a directory with modified files and verify that the changes are correctly reflected in the database, including the creation of new records with links to the old ones.

**Acceptance Scenarios**:

1. **Given** a file has been edited (same path and name, different MD5), **When** the user runs the `update` command, **Then** a new record should be created for the file with a reference to the old record, and the old record should be marked as `deleted`.
2. **Given** a file has been moved to a new directory, **When** the user runs the `update` command, **Then** a new record should be created for the file at its new location with a reference to the old record, and the old record should be marked as `deleted`.
3. **Given** a file has been renamed, **When** the user runs the `update` command, **Then** a new record should be created for the file with its new name with a reference to the old record, and the old record should be marked as `deleted`.

---

### Edge Cases

- What happens when the application encounters a file that it cannot read?
- How does the system handle very large media libraries?
- What happens if the user tries to reorganize files to a location that does not exist?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST be able to scan folders of media files (photos and videos).
- **FR-002**: The system MUST be able to identify duplicate files using MD5 hashes.
- **FR-003**: The system MUST be able to identify related files using perceptual hashes and metadata.
- **FR-004**: The system MUST store file metadata and duplicate information in a database.
- **FR-005**: The system MUST allow users to move duplicate files to a specified folder.
- **FR-006**: The system MUST allow users to reorganize files by date, location, and custom tags. When reorganizing, the application MUST update the existing file record's `path` and `name` fields (in-place update, not a new insert) and preserve `original_path` and `original_name`.
- **FR-007**: The system MUST allow users to add, remove, and view tags for files.
- **FR-008**: The system MUST store its configuration in a `config.json` file.
- **FR-009**: The system MUST display a structured error message (including an error code and brief description) and log detailed error information to a file when an error occurs.
- **FR-010**: The system MUST implement basic logging, recording the start and end of major operations (e.g., a scan) and any errors that occur.
- **FR-011**: The system MUST support exporting data (e.g., a list of duplicates, tags) to common formats like CSV or JSON.
- **FR-012**: The system MUST allow users to rename files based on a predefined format in the configuration file, supporting placeholders for metadata (e.g., MD5, YYYY, MM, DD, PHASH, related_id) and a `datetype` indicator for date sources (0 for Exif, 1 for manual, 8 for literal YYYY-MM-DD, 9 for file creation time).
- **FR-013**: The system MUST store the original filename in the database.
- **FR-014**: The system MUST update the filename in the database when the file is renamed.
- **FR-015**: The system MUST provide a command-line interface for CRUD operations on the `related_id` for each file.
- **FR-016**: The `related_id` MUST be a unique, auto-incremented value for each new image (unique MD5) that does not already exist in the database.
- **FR-017**: The system MUST allow users to add a set of images to a `related_id`.
- **FR-018**: The system MUST allow users to update the `related_id` of the latest image in a set to a user-specified value.
- **FR-019**: If an image has the same MD5 hash as an existing image in the database, the system MUST assign the same `related_id` to it.
- **FR-020**: When renaming files, if a filename conflict occurs, the system MUST append a unique identifier to the subsequent files to prevent data loss (e.g., `{MD5}{whatever}{auto-unique for 2nd duplicate}`).
- **FR-021**: When a file is physically deleted or a new version is created, the system MUST set the `status` field to `deleted` (not a separate boolean flag).
- **FR-022**: The system MUST automatically populate `created_at` and `updated_at` timestamps for each file entry in the database.
- **FR-023**: The system MUST store the original path of the file when the entry is created.
- **FR-024**: The `File` entity MUST have a `status` field with possible values: `new`, `scanned`, `duplicate`, `deleted`.
- **FR-025**: The system MUST record the source of the geocoding data in the `geocode_provenance` field (e.g., `geonames`, `manual`, `utility_X`).
- **FR-026**: If GPS coordinates are present (from EXIF or manual entry), the system MUST resolve them to the nearest available city and country, regardless of the distance.
- **FR-027**: The system MUST provide an `update` command to rescan a directory and detect changes.
- **FR-028**: When an updated file is detected (same path and name, different MD5), the system MUST create a new record and link it to the old record via the `previous_version_id` field.
- **FR-029**: When a moved or renamed file is detected (new path or name, same MD5), the system MUST create a new record and link it to the old record.
- **FR-030**: When a new version of a file is created, the old record MUST be marked with a status of `deleted`.
- **FR-031**: During reorganization, the original filename MUST be preserved in the database and not affected by multiple reorganizations.
- **FR-032**: The reorganization feature MUST provide an option to collate extra duplicates into a pre-defined folder for manual verification.
- **FR-033**: When a collated duplicate file is deleted manually, the system MUST provide a way to mark the corresponding record with a status of `deleted`.
- **FR-034**: The system MUST identify and group files as related (using the `related_id`) if they were taken at the same location (GPS coordinates) and within a user-configurable time threshold.
- **FR-035**: The system MUST use the `exiftool.exe` executable to retrieve raw EXIF data from files, store this raw data in a separate `ExifData` table, and then use this data to populate the relevant fields in the main `File` table.
- **FR-036**: During long-running operations like scanning, the system MUST report progress by printing the index of the current file being processed and the total number of files to the console.

### Key Entities *(include if feature involves data)*

- **File**: Represents a media file, with attributes such as path, name, size, MD5 hash, perceptual hash, tags, status, geocode_provenance, and content_identifier.
- **Tag**: Represents a custom tag that can be applied to a file.
- **ExifData**: Represents the raw EXIF data for a file.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** (Performance - Aspirational): Process 100,000 JPEG files (avg 5MB) on reference hardware (quad-core, SSD) in under 1 hour with full EXIF extraction and hashing.
  - *Acceptance*: CLI reports total scan time; tested on synthetic dataset.

- **SC-002** (Duplicate Detection - Testable): MD5-based duplicate detection achieves 100% accuracy on test dataset with known duplicates.
  - *Acceptance*: Integration test with 1000 files including 50 known duplicate pairs.

- **SC-003** (Usability - Measurable): CLI returns exit code 0 and completes operation for 95% of valid input combinations.
  - *Acceptance*: Integration test suite covering scan, duplicates, reorganize with valid inputs; <5% error rate.

## Assumptions

- The user has a basic understanding of the command line.
- The media files are stored on a local drive or network mapped NAS.
- The user has the necessary permissions to read and write to the media folders.
- The user is responsible for manually updating the database when files are moved or deleted outside of the application.
- The application is assumed to be running in a trusted user environment, and no specific security features against malicious file inputs are implemented.

## Out of Scope

- Real-time file system monitoring
- Cloud storage integration
- Advanced image editing capabilities
- Accessibility features for screen readers or other assistive technologies.

## Terminology

- **perceptual_hash** (also abbreviated as `phash` in code): A hash computed using the imagehash library to detect visually similar images. Stored in the `File.perceptual_hash` column.
- **content_identifier**: An Apple-specific identifier (e.g., for Live Photos) to group related assets from the same device. Not the same as `related_id`.
- **related_id**: A user-managed or auto-assigned ID to group semantically related files (e.g., burst photos, files from same event).