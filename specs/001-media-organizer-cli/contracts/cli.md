# CLI Contracts: Media Organizer CLI

## Commands

### `scan`

-   **Description**: Scans a folder for media files and populates the database.
-   **Usage**: `media-organizer scan <folder_path>`
-   **Options**:
    -   `--rescan`: Forces a rescan of all files, even if they are already in the database.

### `duplicates`

-   **Description**: Finds and manages duplicate files.
-   **Usage**: `media-organizer duplicates`
-   **Options**:
    -   `--move-to <folder_path>`: Moves all duplicate files to the specified folder.

### `reorganize`

-   **Description**: Reorganizes media files into a new folder structure.
-   **Usage**: `media-organizer reorganize <source_folder> <destination_folder>`
-   **Options**:
    -   `--by-date`: Reorganizes files by date (YYYY/MM/DD).
    -   `--by-location`: Reorganizes files by location.
    -   `--by-tag`: Reorganizes files by tag.
    -   `--rename`: Renames files based on the format specified in the configuration file.

### `tag`

-   **Description**: Manages tags for media files.
-   **Usage**: `media-organizer tag <file_path> <tag_name>`
-   **Subcommands**:
    -   `add`: Adds a tag to a file.
    -   `remove`: Removes a tag from a file.
    -   `list`: Lists all tags for a file.

### `related-id`

-   **Description**: Manages the related ID for media files.
-   **Usage**: `media-organizer related-id <related_id> [file_paths...]`
-   **Options**:
    -   `--update-latest <file_path>`: Updates the related ID of the latest image in a set to the specified related ID.
    -   `--delete`: Deletes the related ID for a file.
