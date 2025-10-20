# CLI Contracts

This document defines the command-line interface for the Media Organizer CLI.

## Main Command

The main entry point for the application is `dupdetector`.

## Commands

### `scan`

Scans a directory for media files and adds them to the database.

**Usage:**

```
dupdetector scan <path> [options]
```

**Arguments:**

*   `<path>`: The path to the directory to scan.

**Options:**

*   `--config <path>`: Path to a custom configuration file.
*   `--recursive`: Scan subdirectories recursively.

### `duplicates`

Finds and manages duplicate files.

**Usage:**

```
dupdetector duplicates [options]
```

**Options:**

*   `--move-to <path>`: Moves duplicate files to the specified directory.
*   `--list`: Lists all duplicate files.

### `reorganize`

Reorganizes files into a new directory structure.

**Usage:**

```
dupdetector reorganize <source_path> <destination_path> [options]
```

**Arguments:**

*   `<source_path>`: The path to the directory to reorganize.
*   `<destination_path>`: The path to the destination directory.

**Options:**

*   `--by-date`: Reorganize files by date (YYYY/MM/DD).
*   `--by-location`: Reorganize files by location (Country/City).
*   `--by-tag`: Reorganize files by tag.
*   `--rename`: Rename files based on the format in the configuration file.

### `tag`

Manages tags for files.

**Usage:**

```
dupdetector tag <file_path> <tag_name>
```

**Arguments:**

*   `<file_path>`: The path to the file to tag.
*   `<tag_name>`: The name of the tag to add.

**Subcommands:**

*   `add`: Adds a tag to a file.
*   `remove`: Removes a tag from a file.
*   `list`: Lists all tags for a file.

### `related-id`

Manages related IDs for files.

**Usage:**

```
dupdetector related-id <file_path> [options]
```

**Arguments:**

*   `<file_path>`: The path to the file.

**Options:**

*   `--set <id>`: Sets the related ID for the file.
*   `--update-latest`: Updates the related ID of the latest image in a set.