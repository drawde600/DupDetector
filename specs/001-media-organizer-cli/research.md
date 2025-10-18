# Research: Media Organizer CLI

## Research Findings

-   **Decision**: `imagehash` will be used for image hashing, `SQLAlchemy` will be used for database access, and `ExifTool.exe` will be used for metadata extraction.
    -   **Rationale**: `imagehash` is a popular and efficient library for perceptual image hashing. `SQLAlchemy` provides a powerful and flexible ORM for database interactions, which aligns with the goal of having a database abstraction layer for future MySQL support. `ExifTool.exe` is a powerful command-line tool for reading and writing metadata in a wide variety of file types.
    -   **Alternatives considered**: `Pillow` for image hashing (less robust for perceptual hashing) and `sqlite3` (lower-level, less flexible than SQLAlchemy).