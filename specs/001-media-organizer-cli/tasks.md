# Tasks: Media Organizer CLI

**Input**: Design documents from `/specs/001-media-organizer-cli/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

```markdown
# Tasks: Media Organizer CLI

**Input**: Design documents from `/specs/001-media-organizer-cli/`
**Generated**: by `/specify.task` on 2025-10-18

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Initialize repository layout and documentation (`.`)
- [ ] T002 Initialize Python project and lock dependencies (`pyproject.toml` / `requirements.txt`)
- [ ] T003 [P] Create `examples/config.json` and document configuration keys (`examples/config.json`)
- [ ] T004 [P] Configure linting and formatting (ruff/black/isort) and add workflow (`.github/workflows/lint.yml`)

---

## Phase 2: Foundational (Blocking Prerequisites)

- [ ] T005 Setup initial DB schema and migrations (Alembic) for `src/models` and create `migrations/` (`src/models/, migrations/`)
- [ ] T006 [P] Implement database abstraction layer and connection helpers (`src/lib/database.py`)
- [ ] T007 [P] Implement ExifTool wrapper and path validation (`src/lib/exiftool.py`)
- [ ] T008 Implement logging and structured log file output (`src/lib/logger.py`)
- [ ] T009 Implement configuration management and validation (schema + config loader) (`src/lib/config.py`)

---

## Phase 3: User Story 1 - Duplicate Detection (Priority: P1)

**Goal**: Scan media folders and identify duplicate files.

**Independent Test Criteria**: A sample dataset with known duplicates (in `tests/fixtures/duplicates/`) when scanned will populate the DB and the `duplicates` command will report the expected duplicate groups.

### Test

- [ ] T010 [US1] Create integration test fixture and test harness for duplicate detection (`tests/integration/test_duplicate_detection.py`)

### Implementation

- [ ] T011 [US1] Implement `scan` CLI command and folder walker (`src/cli/scan.py`)
- [ ] T012 [P] [US1] Implement MD5 hashing utility and unit tests (`src/lib/hashing.py`, `tests/unit/test_hashing.py`)
- [ ] T013 [P] [US1] Implement image hashing (phash) utility with configurable threshold (`src/lib/imagehashing.py`, `tests/unit/test_imagehashing.py`)
- [ ] T014 [US1] Implement duplicate detection service and DB population (`src/services/duplicate_detector.py`)
- [ ] T015 [US1] Implement `duplicates` CLI command and `--move-to` option wired to service (`src/cli/duplicates.py`)

### Post-conditions / data

- [ ] T016 [US1] Persist `md5_hash`, `photo_hash`, `is_duplicate`, and `duplicate_of_id` when duplicates are detected (`src/models/file.py`, migration)

---

## Phase 4: User Story 2 - File Reorganization (Priority: P2)

**Goal**: Reorganize media files into a new folder structure by date, location, or tags.

**Independent Test Criteria**: Given `tests/fixtures/reorganize/` input, running `reorganize` with `--by-date` or `--by-tag` moves files to the expected folder layout under a temporary `out/` directory.

### Test

- [ ] T017 [US2] Add integration test for `reorganize --by-date` and `--by-tag` (`tests/integration/test_reorganize.py`)

### Implementation

- [ ] T018 [US2] Implement `reorganize` CLI command with `--by-date`, `--by-location`, `--by-tag`, and `--rename` flags (`src/cli/reorganize.py`)
- [ ] T019 [P] [US2] Implement reorganization by date (year/month/day and configurable depth) (`src/services/reorganizer.py`)
- [ ] T020 [P] [US2] Implement reorganization by location (GPS -> place resolution stub) (`src/services/reorganizer.py`)
- [ ] T021 [P] [US2] Implement reorganization by tag (`src/services/reorganizer.py`)
- [ ] T022 [US2] Implement rename handling and DB update on rename (`src/services/reorganizer.py`, `src/services/database.py`)

---

## Phase 5: User Story 3 - Tagging (Priority: P3)

**Goal**: Add, remove, and view tags for media files.

**Independent Test Criteria**: Unit and integration tests that add/remove/list tags via CLI and assert DB state and CLI output.

### Test

- [ ] T023 [US3] Add unit and integration tests for tag commands (`tests/unit/test_tag.py`, `tests/integration/test_tag_cli.py`)

### Implementation

- [ ] T024 [US3] Implement `tag` CLI command and subcommands `add`, `remove`, `list` (`src/cli/tag.py`)
- [ ] T025 [P] [US3] Implement Tag model and `FileTag` join table and service helpers (`src/models/tag.py`, `src/services/tag_service.py`)

---

## Phase 6: User Story 4 - File Renaming (Priority: P4)

**Goal**: Rename media files according to config-defined templates and handle conflicts safely.

**Independent Test Criteria**: Integration test that runs `reorganize --rename` and verifies names, DB updates, and unique suffix behavior on conflict.

- [ ] T026 [US4] Add integration test for rename behavior (`tests/integration/test_rename.py`)
- [ ] T027 [US4] Implement rename template parser and available tokens (`src/lib/rename.py`)
- [ ] T028 [US4] Implement conflict resolution and unique suffix strategy (`src/services/reorganizer.py`)
- [ ] T029 [US4] Ensure DB `original_name` and `name` are updated atomically on rename (`src/services/database.py`)

---

## Phase 7: User Story 5 - Related ID Management (Priority: P5)

**Goal**: Assign and manage `related_id` to group related media files.

**Independent Test Criteria**: Unit tests for related-id assignment rules and CLI tests for group assignment and update-latest behavior.

- [ ] T030 [US5] Add unit tests for `related_id` auto-increment and assignment (`tests/unit/test_related_id.py`)
- [ ] T031 [US5] Implement `related-id` CLI command and subcommands (`src/cli/related_id.py`)
- [ ] T032 [US5] Implement DB routines for auto-incrementing `related_id` and MD5-based assignment (`src/services/database.py`)
- [ ] T033 [US5] Implement `--update-latest` behavior and CLI handler (`src/cli/related_id.py`)

---

## Phase 8: Cross-cutting & Polish

- [ ] T034 [P] Create export functionality (CSV/JSON) and CLI hooks (`src/services/exporter.py`, `src/cli/export.py`)
- [ ] T035 Add `rescan` behavior implementation and `--rescan` handling for `scan` (`src/cli/scan.py`, `src/services/duplicate_detector.py`)
- [ ] T036 Implement `is_deleted` detection and CLI to mark entries as deleted and garbage-collect (`src/services/deletion.py`, `src/cli/admin.py`)
- [ ] T037 Ensure DB timestamps `created_at` and `updated_at` are set and updated by ORM (`src/models/file.py`, migrations)
- [ ] T038 [P] Add profiling harness and measurable performance tests for SC-001 (`tests/perf/test_perf_baseline.py`, `tools/profiler/`)
- [ ] T039 [P] Implement security checks for file operations (validate paths, avoid race conditions) (`src/lib/safe_ops.py`)
- [ ] T040 [P] Documentation: update `README.md`, `quickstart.md`, and `docs/` (`README.md`, `specs/001-media-organizer-cli/quickstart.md`)
- [ ] T041 Code cleanup, type hints, and lint fixes across `src/` (`src/`)
- [ ] T042 Add CI job to run unit and integration tests (`.github/workflows/ci.yml`)
- [ ] T043 Run `quickstart.md` validation (verify sample commands work with new CLI) (`specs/001-media-organizer-cli/quickstart.md`)

---

## Dependencies (high-level user story completion order)

1. Phase 1 (T001-T004) must be complete before foundational work.
2. Phase 2 (T005-T009) must be complete before Story implementations.
3. Story phases executed in priority order: US1 (T010-T016) → US2 (T017-T022) → US3 (T023-T025) → US4 (T026-T029) → US5 (T030-T033).
4. Cross-cutting tasks (T034-T043) can run in parallel where marked [P].

## Parallel execution examples

- Example A (parallel workers): T012 (MD5 hashing) and T013 (image hashing) can run in parallel across file batches — mark both [P].
- Example B (CI & docs): T042 (CI) and T040 (docs) can be worked on in parallel by different contributors — both [P].
- Example C (foundational parallel): T006 (DB abstraction) and T007 (ExifTool wrapper) are parallelizable implementation tasks — both [P].

## Implementation strategy (MVP-first, incremental)

- MVP scope suggestion: Deliver **User Story 1 (Duplicate Detection)** end-to-end (T010–T016) plus foundational DB/config (T005, T006, T009) and one integration test (T010). This provides a usable CLI `scan` + `duplicates` and is testable.
- Iteration 2: Add reorganization (US2 T017–T022) and tagging (US3 T023–T025).
- Iteration 3: Renaming and related-id features (US4, US5), polish and performance optimizations.

## Task counts & mapping

- Total tasks: 43 (T001–T043)
- Tasks by story:
	- US1: 7 tasks (T010–T016)
	- US2: 6 tasks (T017–T022)
	- US3: 3 tasks (T023–T025)
	- US4: 4 tasks (T026–T029)
	- US5: 4 tasks (T030–T033)
	- Setup/Foundational/Cross-cutting: 19 tasks (T001–T009, T034–T043)

## Format validation

- All tasks begin with a checklist (`- [ ]`), include a TaskID `T###`, story label `[USn]` for story tasks, `[P]` only where parallelizable, and end with a file or path reference.

## Notes

- I added automated test tasks because the feature spec includes mandatory testing scenarios and to align with best practices. If you prefer manual-only tests, I can remove or reclassify test tasks.

```
