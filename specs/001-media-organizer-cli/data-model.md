# Data Model: Media Organizer CLI

## Entities

### File

| Column | Type | Constraints |
|---|---|---|
| id | INTEGER | Primary Key, NOT NULL |
| path | TEXT | UNIQUE, NOT NULL |
| original_path | TEXT | NOT NULL |
| name | TEXT | NOT NULL |
| original_name | TEXT | NOT NULL |
| size | INTEGER | NOT NULL |
| media_type | TEXT | NULLABLE |
| dimensions | TEXT | NULLABLE |
| manufacturer | TEXT | NULLABLE |
| gps | TEXT | NULLABLE |
| metadata | TEXT | NULLABLE |
| md5_hash | TEXT | NOT NULL |
| photo_hash | TEXT | NULLABLE |
| related_id | INTEGER | NULLABLE |
| is_duplicate | BOOLEAN | NOT NULL, DEFAULT false |
| is_deleted | BOOLEAN | NOT NULL, DEFAULT false |
| created_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP |
| updated_at | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP |
| duplicate_of_id | INTEGER | NULLABLE, Foreign Key to File.id |

### Tag

-   **id**: INTEGER (Primary Key)
-   **name**: TEXT (UNIQUE)

### FileTag

-   **file_id**: INTEGER (Foreign Key to File.id)
-   **tag_id**: INTEGER (Foreign Key to Tag.id)
