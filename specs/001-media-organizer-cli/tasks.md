# Tasks: Media Organizer CLI

**Input**: Design documents from `/specs/001-media-organizer-cli/`

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Initialize Python project and dependencies (`pyproject.toml` / `requirements.txt`)
- [ ] T002 [P] Create `config.json` and document configuration keys (`config.json`)
- [ ] T003 [P] Configure linting and formatting (ruff/black/isort) and add workflow (`.github/workflows/lint.yml`)

---

## Phase 2: Foundational (Blocking Prerequisites)

- [ ] T004 Setup initial DB schema and migrations (Alembic) for `src/models` (`src/models`, `alembic/`)
- [ ] T005 [P] Implement database abstraction layer and connection helpers (`src/lib/database.py`)
- [ ] T006 [P] Implement ExifTool wrapper and path validation (`src/lib/exiftool.py`)
- [ ] T007 Implement logging and structured log file output (`src/lib/logger.py`)
- [ ] T008 Implement configuration management and validation (`src/lib/config.py`)
- [ ] T008a [P] Document all config keys in README and validate schema (`src/lib/config.py`, `README.md`)

---

## Phase 3: MVP - Initial Scan

**Goal**: Scan media folders, extract metadata, and populate the database.

**Independent Test Criteria**: A sample dataset with various media files, when scanned, will populate the database with correct metadata (hashes, EXIF, etc.).

### Test

- [ ] T009a [MVP] Create synthetic test fixture dataset (10 images, 2 duplicates, EXIF variety) (`tests/fixtures/media_samples/`)
- [ ] T009b [MVP] Create integration test for initial scan using fixture dataset (`tests/integration/test_scan.py`)

### Implementation

- [ ] T010 [MVP] Implement `scan` CLI command and folder walker (`src/cli/scan.py`)
- [ ] T011 [P] [MVP] Implement MD5 hashing utility (`src/lib/hashing.py`)
- [ ] T012 [P] [MVP] Implement image hashing (phash) utility (`src/lib/hashing.py`)
- [ ] T013 [MVP] Implement service to handle file scanning, metadata extraction, and database population (`src/services/scanner.py`)
- [ ] T014a [MVP] Implement config precedence loader (CLI flag > CWD > package default) (`src/lib/config.py`)
- [ ] T014b [MVP] Implement ExifTool path validation and executable check (`src/lib/preflight.py`)
- [ ] T014c [MVP] Implement geodatabase reachability check with 5s timeout (`src/lib/preflight.py`)
- [ ] T014d [MVP] Implement main database connection fallback to SQLite (`src/lib/preflight.py`)
- [ ] T014e [MVP] Implement candidate file counter (diagnostic, non-blocking) (`src/lib/preflight.py`)
- [ ] T014f [MVP] Wire all preflight checks into scan CLI startup (`src/cli/scan.py`)

---

## Phase 4: User Story 1 - Duplicate Detection

- [ ] T015 [US1] Implement duplicate detection service (`src/services/duplicates.py`)
- [ ] T016 [US1] Implement `duplicates` CLI command (`src/cli/duplicates.py`)

---

## Phase 5: User Story 2 - File Reorganization

- [ ] T017 [US2] Implement `reorganize` CLI command (`src/cli/reorganize.py`)
- [ ] T018 [US2] Implement reorganization service (`src/services/reorganizer.py`)
- [ ] T018a [US2] Implement database path/name update during reorganization (update existing record, not insert) (`src/services/reorganizer.py`)

---

## Phase 6: User Story 3 - Tagging

- [ ] T019 [US3] Implement tag data model and repository methods (`src/models/tag.py`, `src/services/repository.py`)
- [ ] T020 [US3] Implement `tag add` CLI command (`src/cli/tag.py`)
- [ ] T021 [US3] Implement `tag remove` CLI command (`src/cli/tag.py`)
- [ ] T022 [US3] Implement `tag list` CLI command (`src/cli/tag.py`)
- [ ] T023 [US3] Create integration tests for tag CRUD operations (`tests/integration/test_tags.py`)

---

## Phase 7: Data Export

- [ ] T024 Implement export service with CSV and JSON formatters (`src/services/exporter.py`)
- [ ] T025 Implement `export duplicates` CLI command (`src/cli/export.py`)
- [ ] T026 Implement `export tags` CLI command (`src/cli/export.py`)
- [ ] T027 Create integration tests for export functionality (`tests/integration/test_export.py`)

---

## Phase 8: User Story 5 - Related ID Management

- [ ] T028 [US5] Implement related_id auto-increment logic in repository layer (`src/services/repository.py`)
- [ ] T029 [US5] Implement `related-id set` CLI command (`src/cli/related_id.py`)
- [ ] T030 [US5] Implement `related-id update-latest` CLI command (`src/cli/related_id.py`)
- [ ] T031 [US5] Implement MD5-based related_id inheritance on duplicate insert (`src/services/scanner.py`)
- [ ] T032 [US5] Create integration tests for related_id operations (`tests/integration/test_related_id.py`)

---

## Phase 9: User Story 7 - Rescan and Update

- [ ] T033 [US7] Implement file change detection service (MD5 comparison) (`src/services/change_detector.py`)
- [ ] T034 [US7] Implement version linking logic (previous_version_id) (`src/services/repository.py`)
- [ ] T035 [US7] Implement `update` CLI command with directory rescan (`src/cli/update.py`)
- [ ] T036 [US7] Create integration tests for rescan scenarios (edit/move/rename) (`tests/integration/test_update.py`)

---

## Phase 10: User Story 4 - File Renaming

- [ ] T037 [US4] Implement rename format parser with placeholders (MD5, YYYY, PHASH, etc.) (`src/lib/renaming.py`)
- [ ] T038 [US4] Implement collision detection and unique suffix generation (`src/lib/renaming.py`)
- [ ] T039 [US4] Integrate rename logic into reorganize service (`src/services/reorganizer.py`)
- [ ] T040 [US4] Create integration tests for renaming with conflicts (`tests/integration/test_rename.py`)

---

## Phase 11: User Story 6 - Post-Scan GPS Updates

- [ ] T041 [US6] Implement GPS update service with geocoding (`src/services/gps_updater.py`)
- [ ] T042 [US6] Implement `gps update` CLI command (`src/cli/gps.py`)
- [ ] T043 [US6] Add geocode_provenance tracking (manual vs geonames) (`src/services/gps_updater.py`)
- [ ] T044 [US6] Create integration tests for GPS update scenarios (`tests/integration/test_gps_update.py`)

---

## Phase 12: Auto-Clustering by GPS and Time

- [ ] T045 Implement GPS proximity calculator (haversine distance) (`src/lib/geo.py`)
- [ ] T046 Implement time threshold clustering service (`src/services/clustering.py`)
- [ ] T047 Add `related_time_threshold_minutes` to config validation (`src/lib/config.py`)
- [ ] T048 Integrate auto-clustering into scan workflow (optional flag) (`src/services/scanner.py`)
- [ ] T049 Create integration tests for GPS/time clustering (`tests/integration/test_clustering.py`)

---

## Implementation Strategy (MVP-first, incremental)

- **MVP scope**: Deliver the **Initial Scan** functionality end-to-end (T009–T014) plus foundational DB/config (T004-T008). This provides a usable CLI `scan` command that populates the database.
- **Iteration 2**: Add duplicate detection (US1).
- **Iteration 3**: Add file reorganization (US2) and other features.