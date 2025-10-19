# DupDetector Constitution

## Core Principles

### I. CLI-First Development

Every feature MUST be exposed through a command-line interface.

- Commands follow the pattern: `dupdetector <command> [args] [options]`
- All operations must be scriptable and automatable
- Text in/out protocol: args → stdout, errors → stderr
- Support for both human-readable and machine-parseable output (where applicable)
- Exit codes: 0 for success, non-zero for errors

### II. Automated Testing (NON-NEGOTIABLE)

All features MUST include automated tests before merging.

- Tests may be authored in the same PR as the feature (not strict TDD)
- Minimum coverage: Integration tests for user-facing commands
- Unit tests required for: Hashing algorithms, metadata extraction, database operations
- Test fixtures must be reproducible and version-controlled
- Tests must pass on Windows 11 (Command Prompt and PowerShell)

### III. Simplicity and Minimalism

Start simple; complexity must be justified.

- **Default to simple solutions**: Use built-in libraries before adding dependencies
- **YAGNI principle**: Only implement what's needed now, not what might be needed
- **Extensibility over features**: Design for future extension without implementing it
- Every new dependency MUST be justified in PR description or design doc
- Prefer SQLite over complex database setups unless scale demands otherwise

### IV. Windows-First Development

Primary target platform is Windows 11 (Command Prompt and PowerShell).

- All scripts and tools MUST work in Windows Command Prompt and PowerShell
- Path handling MUST use `os.path` or `pathlib` for cross-platform compatibility
- Line endings: Git autocrlf handles conversion; code uses `\n` internally
- External tools (ExifTool, etc.) MUST have Windows-compatible paths configured
- Testing and CI MUST validate on Windows environments

### V. Database as Ground Truth

The database is the authoritative source of file state.

- File metadata (MD5, perceptual hash, EXIF) is computed once during scan
- Database entries persist even when physical files are deleted (use `status='deleted'`)
- No dual tracking: Use single fields for state (e.g., `status`, not `status` + `is_deleted`)
- Original metadata (`original_path`, `original_name`) MUST be preserved across reorganizations
- Database migrations via Alembic; all schema changes documented

## Technology Stack

### Mandatory Components

- **Language**: Python 3.11+
- **Database**: SQLite (default), MySQL/PostgreSQL (optional for scale)
- **ORM**: SQLAlchemy
- **CLI Framework**: Click or argparse
- **Testing**: pytest
- **Image Hashing**: imagehash (PIL/Pillow)
- **EXIF Extraction**: ExifTool (external executable)
- **Geocoding**: Local GeoNames database (MySQL)

### Prohibited Dependencies

- Cloud service integrations (S3, Azure Blob, etc.)
- Real-time file system monitoring frameworks (watchdog, etc.)
- GUI frameworks (tkinter, PyQt, etc.) - CLI only
- Complex workflow orchestration tools (Airflow, Prefect, etc.)

## Development Workflow

### Quality Gates

Every PR MUST satisfy these gates before merge:

1. **Tests pass**: All integration and unit tests pass on Windows 11
2. **Linting passes**: Code conforms to project style (ruff/black/isort)
3. **No regressions**: Existing tests continue to pass
4. **Documentation updated**: README and CLI help text reflect new features

### Complexity Budget

Projects start simple and may grow based on need. Justify added complexity:

| Addition | Requires Justification |
|----------|------------------------|
| New external service | Design doc explaining why local solution insufficient |
| New Python dependency | PR description with alternatives considered |
| Architecture pattern (Repository, Service Layer, etc.) | Document in `plan.md` with rationale |
| Third database engine | Performance benchmarks showing SQLite bottleneck |

### Extension Philosophy

**Build for extension, not speculation:**

- Design interfaces that *could* support future features (e.g., pluggable hash algorithms)
- Do NOT implement the future features until needed
- Document extension points in docstrings or `plan.md`
- Prefer configuration over hardcoding (but don't over-configure)

Example: Support for future cloud storage could be designed via an abstract `Storage` interface, but only implement `LocalFileStorage` until cloud support is explicitly requested.

## Governance

### Authority

This constitution supersedes all other development practices. Where conflicts arise, constitution principles take precedence.

### Amendments

Constitution changes require:

1. Explicit discussion and agreement (document in `CONSTITUTION_CHANGES.md` or spec notes)
2. Update to this file with rationale
3. Update of `Last Amended` timestamp
4. Communication to all contributors

### Compliance

- All PRs must be reviewed for constitutional compliance
- Violations are grounds for PR rejection
- Principles marked NON-NEGOTIABLE cannot be waived without amendment

**Version**: 1.0.0 | **Ratified**: 2025-10-19 | **Last Amended**: 2025-10-19
