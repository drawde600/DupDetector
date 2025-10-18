# Tasks: Media Organizer CLI

**Input**: Design documents from `/specs/001-media-organizer-cli/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create project structure per implementation plan
- [ ] T002 Initialize Python project with dependencies (`imagehash`, `SQLAlchemy`)
- [ ] T003 [P] Configure linting and formatting tools

---

## Phase 2: Foundational (Blocking Prerequisites)

- [ ] T004 Setup database schema and migrations framework
- [ ] T005 [P] Implement database abstraction layer in `src/lib/database.py`
- [ ] T006 [P] Implement ExifTool wrapper in `src/lib/exiftool.py`
- [ ] T007 Implement logging in `src/lib/logger.py`
- [ ] T008 Implement configuration management in `src/lib/config.py`

---

## Phase 3: User Story 1 - Duplicate Detection

**Goal**: Scan media folders and identify duplicate files.

**Independent Test**: Run the application on a folder with known duplicate files and verify that the duplicates are correctly identified.

### Implementation for User Story 1

- [ ] T009 [US1] Implement `scan` command in `src/cli/scan.py`
- [ ] T010 [P] [US1] Implement MD5 hashing in `src/lib/hashing.py`
- [ ] T011 [P] [US1] Implement image hashing in `src/lib/hashing.py`
- [ ] T012 [US1] Implement duplicate detection logic in `src/services/duplicate_detector.py`
- [ ] T013 [US1] Implement `duplicates` command in `src/cli/duplicates.py`

---

## Phase 4: User Story 2 - File Reorganization

**Goal**: Reorganize media files into a new folder structure.

**Independent Test**: Run the reorganization command on a folder of media files and verify that the files are moved to the correct new folder structure.

### Implementation for User Story 2

- [ ] T014 [US2] Implement `reorganize` command in `src/cli/reorganize.py`
- [ ] T015 [P] [US2] Implement reorganization by date in `src/services/reorganizer.py`
- [ ] T016 [P] [US2] Implement reorganization by location in `src/services/reorganizer.py`
- [ ] T017 [P] [US2] Implement reorganization by tag in `src/services/reorganizer.py`

---

## Phase 5: User Story 3 - Tagging

**Goal**: Add, remove, and view tags for media files.

**Independent Test**: Add, remove, and view tags for a media file and verify that the tags are correctly applied.

### Implementation for User Story 3

- [ ] T018 [US3] Implement `tag` command in `src/cli/tag.py`
- [ ] T019 [P] [US3] Implement `add` subcommand in `src/cli/tag.py`
- [ ] T020 [P] [US3] Implement `remove` subcommand in `src/cli/tag.py`
- [ ] T021 [P] [US3] Implement `list` subcommand in `src/cli/tag.py`

---

## Phase 6: User Story 4 - File Renaming

**Goal**: Rename media files based on a predefined format.

**Independent Test**: Run the reorganization command with the `--rename` option and verify that the files are renamed according to the specified format.

### Implementation for User Story 4

- [ ] T022 [US4] Implement `--rename` option for `reorganize` command in `src/cli/reorganize.py`
- [ ] T023 [US4] Implement filename conflict resolution in `src/services/reorganizer.py`

---

## Phase 7: User Story 5 - Related ID Management

**Goal**: Assign a related ID to media files to group them together.

**Independent Test**: Add, remove, and view a related ID for a media file and verify that the related ID is correctly applied.

### Implementation for User Story 5

- [ ] T024 [US5] Implement `related-id` command in `src/cli/related_id.py`
- [ ] T025 [US5] Implement auto-incrementing `related_id` in `src/services/database.py`
- [ ] T026 [US5] Implement assigning `related_id` based on MD5 hash in `src/services/database.py`
- [ ] T027 [US5] Implement adding a set of images to a `related_id` in `src/cli/related_id.py`
- [ ] T028 [US5] Implement updating `related_id` of the latest image in a set in `src/cli/related_id.py`

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T029 [P] Documentation updates in `docs/`
- [ ] T030 Code cleanup and refactoring
- [ ] T031 Performance optimization across all stories
- [ ] T032 Security hardening
- [ ] T033 Run quickstart.md validation
