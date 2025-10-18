# Feature Specification: Media Organizer CLI

**Feature Branch**: `001-media-organizer-cli`  
**Created**: 2025-10-18  
**Status**: Draft  
**Input**: User description: "Build a command application that can help me organize my media files (photos and videos) check all the folders. Determine if there are duplicates (using md5) or related (some means to detect associated, date/time taken, metadata of apple content identifier, similarity of photo (photo hash). Store in database to minimize re-calculation, database can be re-fresh/recalculated might be due to new algo. Allow special Folder to dump duplicate, duplicates also marked in db as field. Original name stored in db. Allow to reorganize to flat mode, by date (multi-level : year only, year-month, year-month-day), by location, by custom tag. The configuration of the application is stored as json (config.json). Tagging can be done per file,files or directory. CRUD operations for tagging, there might be more than 1 tags per file. identical (md5 similar) files are expected to have same set of tags."

## Clarifications

### Session 2025-10-18

- Q: What should happen to the database entry when a file is moved or deleted outside of the application? → A: The user is responsible for manually updating the database when files are moved or deleted.
- Q: How should the application handle errors, such as when a file cannot be read or a folder cannot be accessed? → A: The application should display a user-friendly error message and log the detailed error information to a file.
- Q: What level of logging should be implemented? → A: Basic logging of major events and errors.
- Q: Should the application support importing or exporting data (e.g., the database or a list of duplicates)? → A: Yes, the application should support exporting data (e.g., a list of duplicates, tags) to a common format like CSV or JSON.
- Q: What features are explicitly out of scope for this version of the application? → A: Real-time file system monitoring, cloud storage integration, and advanced image editing capabilities are out of scope.
- Q: How should the application handle database entries for physically deleted files? → A: Add a `is_deleted` flag to the `File` table to mark entries as deleted.
- Q: Should the `File` table have separate columns for each metadata attribute, or should all additional metadata be stored in a single `metadata` column (e.g., as a JSON object)? → A: Use separate columns for each metadata attribute.

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

As a user, I want to be able to reorganize my media files into a new folder structure based on date, location, or custom tags.

**Why this priority**: This feature provides a powerful way for users to organize their media library.

**Independent Test**: The user can run the reorganization command on a folder of media files and verify that the files are moved to the correct new folder structure.

**Acceptance Scenarios**:

1. **Given** a folder of media files, **When** the user runs the reorganization command with the `by-date` option, **Then** the files should be moved to a new folder structure organized by year, month, and day.
2. **Given** a folder of media files, **When** the user runs the reorganization command with the `by-location` option, **Then** the files should be moved to a new folder structure organized by location.

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

### Edge Cases

- What happens when the application encounters a file that it cannot read?
- How does the system handle very large media libraries?
- What happens if the user tries to reorganize files to a location that does not exist?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST be able to scan folders of media files (photos and videos).
- **FR-002**: The system MUST be able to identify duplicate files using MD5 hashes.
- **FR-003**: The system MUST be able to identify related files using photo hashes and metadata.
- **FR-004**: The system MUST store file metadata and duplicate information in a database.
- **FR-005**: The system MUST allow users to move duplicate files to a specified folder.
- **FR-006**: The system MUST allow users to reorganize files by date, location, and custom tags.
- **FR-007**: The system MUST allow users to add, remove, and view tags for files.
- **FR-008**: The system MUST store its configuration in a `config.json` file.
- **FR-009**: The system MUST display a user-friendly error message and log detailed error information to a file when an error occurs.
- **FR-010**: The system MUST implement basic logging of major events and errors.
- **FR-011**: The system MUST support exporting data (e.g., a list of duplicates, tags) to common formats like CSV or JSON.
- **FR-012**: The system MUST allow users to rename files based on a predefined format in the configuration file, supporting placeholders for metadata (e.g., MD5, YYYY, MM, DD, PHASH, related_id) and a `datatype` indicator for date sources (0 for Exif, 1 for manual, 8 for literal YYYY-MM-DD, 9 for file creation time).
- **FR-013**: The system MUST store the original filename in the database.
- **FR-014**: The system MUST update the filename in the database when the file is renamed.
- **FR-015**: The system MUST provide a command-line interface for CRUD operations on the `related_id` for each file.
- **FR-016**: The `related_id` MUST be a unique, auto-incremented value for each new image (unique MD5) that does not already exist in the database.
- **FR-017**: The system MUST allow users to add a set of images to a `related_id`.
- **FR-018**: The system MUST allow users to update the `related_id` of the latest image in a set to a user-specified value.
- **FR-019**: If an image has the same MD5 hash as an existing image in the database, the system MUST assign the same `related_id` to it.
- **FR-020**: When renaming files, if a filename conflict occurs, the system MUST append a unique identifier to the subsequent files to prevent data loss (e.g., `{MD5}{whatever}{auto-unique for 2nd duplicate}`).
- **FR-021**: When a file is physically deleted, the system MUST mark its database entry with an `is_deleted` flag and skip it for most operations.
- **FR-022**: The system MUST automatically populate `created_at` and `updated_at` timestamps for each file entry in the database.
- **FR-023**: The system MUST store the original path of the file when the entry is created.

### Key Entities *(include if feature involves data)*

- **File**: Represents a media file, with attributes such as path, name, size, MD5 hash, photo hash, and tags.
- **Tag**: Represents a custom tag that can be applied to a file.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The application should be able to process a 1TB media library with 100,000 files in under 1 hour.
- **SC-002**: The duplicate detection accuracy should be at least 99.9%.
- **SC-003**: 90% of users should be able to successfully organize their media library on the first attempt.

## Assumptions

- The user has a basic understanding of the command line.
- The media files are stored on a local drive or network mapped NAS.
- The user has the necessary permissions to read and write to the media folders.
- The user is responsible for manually updating the database when files are moved or deleted outside of the application.

## Out of Scope

- Real-time file system monitoring
- Cloud storage integration
- Advanced image editing capabilities