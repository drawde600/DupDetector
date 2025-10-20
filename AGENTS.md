# Repository Guidelines

## Project Structure & Module Organization
- `src/dupdetector/` hosts the CLI entrypoint (`cli.py`) plus supporting `lib/`, `services/`, and SQLAlchemy `models/`; keep shared helpers there so the CLI stays thin.
- `alembic/` manages schema versions and generated migrations; the SQLite dev database lives at `dupdetector.db` by default.
- `tests/` mirrors the runtime modules with focused Pytest suites; add new files alongside matching code paths.
- `scripts/` contains operational helpers such as `run_scan_persist.py` (scan and persist pipeline) and scenario seeds.
- `docs/` and `specs/001-media-organizer-cli/` store reference material; consult them before proposing structural changes.

## Build, Test, and Development Commands
- `python -m pip install -r requirements.txt` installs the minimal tooling stack.
- `python -m pytest -q` runs the full test suite; prefer `-k` for targeted runs when iterating.
- `python -m dupdetector.cli scan Z:\path\to\media` executes the scanner with the current `config.json`.
- `python .\scripts\run_scan_persist.py 'Z:\Media' --recursive --db 'sqlite:///Z:/tools/duplicate-detector/dupdetector.db'` drives the end-to-end ingest and persistence flow.
- `alembic upgrade head` applies migrations after you adjust models or ship database changes.

## Coding Style & Naming Conventions
- Target Python 3.11+, four-space indentation, and type-annotated function signatures to match existing modules.
- Keep imports explicit and module-scoped; run `python check_imports.py` if you add dependencies to confirm packages load.
- Model classes follow PascalCase (`File`, `Tag`), service helpers use snake_case modules, and configuration constants stay uppercase.
- Preserve Windows-first ergonomics in examples (PowerShell syntax and backslash paths) as reinforced in `docs/windows.md`.

## Testing Guidelines
- Place tests under `tests/` using the `test_*.py` pattern defined in `pyproject.toml`.
- Cover new repository, hashing, or migration logic with deterministic fixtures; avoid depending on external drives in unit tests.
- Use the SQLite file shipped in the repo for quick checks, but reset or isolate state in fixtures to keep runs idempotent.
- Document manual validation (for example, sample scan paths) in the PR when automated coverage is impractical.

## Commit & Pull Request Guidelines
- Follow the existing `<type>(scope): summary` style (`feat(phash): ...`, `chore(db): ...`) and keep messages in the imperative.
- Group related changes per commit; run tests before pushing and mention the command in the PR description.
- PRs should outline intent, reference related specs or tasks, call out schema updates, and include before or after evidence or logs when touching the CLI.
- Request review once migrations are in place and scripts updated, ensuring docs stay consistent with new behavior.

## Windows & Configuration Tips
- Maintain a valid `config.json`; include sample values when proposing new fields so the default scan remains usable.
- Set `$env:PYTHONPATH = '<repo>\src'` in long-lived shells before running scripts or tests to ensure local imports resolve.
- Prefer PowerShell-native constructs when sharing snippets; provide Bash equivalents only if explicitly needed.
