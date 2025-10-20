import argparse
from pathlib import Path
from typing import Optional, Iterable, Set, Any
import json
import concurrent.futures
import traceback
import time

from dupdetector.lib.hashing import md5_file, phash_stub
from dupdetector.lib.filetype import detect_media_type
from dupdetector.services.repository import Repository


def _iter_files(folder: Path, recursive: bool) -> Iterable[Path]:
    """Iterate over files in folder. Yields only valid files, skipping directories and errors."""
    if recursive:
        for p in folder.rglob("*"):
            try:
                if p.is_file():
                    yield p
            except (OSError, PermissionError):
                # Skip files we can't access
                continue
    else:
        for p in folder.iterdir():
            try:
                if p.is_file():
                    yield p
            except (OSError, PermissionError):
                # Skip files we can't access
                continue


def _exts_from_arg(exts_arg: Optional[str]) -> Optional[Set[str]]:
    if not exts_arg:
        return None
    parts = [e.strip().lower() for e in exts_arg.split(",") if e.strip()]
    normalized = set()
    for p in parts:
        if not p.startswith("."):
            p = "." + p
        normalized.add(p)
    return normalized



def _load_config(path: str, verbose: bool = True) -> dict[str, Any]:
    p = Path(path)
    # Load and parse config file with optional verbose output
    try:
        if not p.exists():
            if verbose:
                print(f"_load_config: path does not exist: {p}")
            return {}
        if verbose:
            print(f"Loading config from: {p}")
        # Read file as text
        try:
            with p.open("r", encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except Exception as e:
            if verbose:
                print(f"ERROR: failed to read config file {p}: {e}")
                traceback.print_exc()
            return {}

        # Parse JSON
        try:
            data = json.loads("\n".join(lines))
            if verbose:
                print(f"Config loaded successfully ({len(lines)} lines)")
            return data
        except Exception as e:
            if verbose:
                print(f"ERROR: failed to parse JSON from {p}: {e}")
                traceback.print_exc()
            return {}
    except Exception as e:
        if verbose:
            print(f"ERROR: unexpected error when loading {p}: {e}")
            traceback.print_exc()
        return {}


def _validate_and_normalize_config(cfg: dict) -> dict:
    out: dict = {}
    # recursive
    out["recursive"] = bool(cfg.get("recursive", False))
    # extensions: accept list or comma string
    exts = cfg.get("extensions")
    if isinstance(exts, list):
        out["extensions"] = [str(e).lower().lstrip(".") for e in exts if e]
    elif isinstance(exts, str):
        out["extensions"] = [e.strip().lower().lstrip(".") for e in exts.split(",") if e.strip()]
    else:
        out["extensions"] = None
    # sizes
    try:
        out["min_size"] = int(cfg.get("min_size")) if cfg.get("min_size") is not None else None
    except Exception:
        out["min_size"] = None
    try:
        out["max_size"] = int(cfg.get("max_size")) if cfg.get("max_size") is not None else None
    except Exception:
        out["max_size"] = None
    return out


def scan(args, session: Optional[object] = None):
    folder = Path(args.folder)
    # Determine config path: if user provided --config, use it. Otherwise look for
    # a `config.json` inside the target folder. Avoid reading a project-root
    # config.json so tests and other folders aren't affected.
    user_cfg = getattr(args, "config", None)
    if user_cfg:
        cfg_path = user_cfg
    else:
        candidate = folder / "config.json"
        cfg_path = str(candidate) if candidate.exists() else None
    # Use verbose=False to avoid redundant config output if already loaded by caller
    raw_cfg = _load_config(cfg_path, verbose=False) if cfg_path else {}
    cfg = _validate_and_normalize_config(raw_cfg)

    # Lightweight validation: warn if geocoding is enabled but local_geonames creds incomplete
    try:
        geocode_cfg = raw_cfg.get("geocode") if isinstance(raw_cfg, dict) else None
        if geocode_cfg and geocode_cfg.get("enabled"):
            providers = geocode_cfg.get("providers") or ([geocode_cfg.get("provider")] if geocode_cfg.get("provider") else [])
            # If local_geonames is expected to be used, ensure required fields are present
            if any(str(p).lower() == "local_geonames" for p in providers):
                lg = geocode_cfg.get("local_geonames", {}) or {}
                missing = [k for k in ("host", "user", "database") if not lg.get(k)]
                if missing:
                    print(f"WARNING: geocode.enabled is true and 'local_geonames' provider is configured, but missing credentials: {', '.join(missing)}. Reverse-geocoding may fail.")
    except Exception:
        # Don't fail startup due to config validation
        pass

    # CLI overrides (if provided) take precedence over config file
    recursive = bool(getattr(args, "recursive", None)) if getattr(args, "recursive", None) is not None else cfg.get("recursive", False)
    exts_arg = getattr(args, "extensions", None)
    if exts_arg:
        exts = _exts_from_arg(exts_arg)
    else:
        exts = { ("." + e) for e in cfg.get("extensions") } if cfg.get("extensions") else None

    # Convert min/max size to int once before loop to avoid repeated conversions and None checks
    min_size_raw = getattr(args, "min_size", None) if getattr(args, "min_size", None) is not None else cfg.get("min_size")
    max_size_raw = getattr(args, "max_size", None) if getattr(args, "max_size", None) is not None else cfg.get("max_size")
    min_size = int(min_size_raw) if min_size_raw is not None else None
    max_size = int(max_size_raw) if max_size_raw is not None else None

    print(f"Scanning folder: {folder} (config={cfg_path}) recursive={recursive} extensions={exts} min_size={min_size} max_size={max_size}")

    repo = None
    if session is not None:
        repo = Repository(session)

    # Determine exiftool path from config (folder-specific or project)
    exiftool_path = None
    exiftool_timeout = 15
    try:
        # raw_cfg is the loaded config for the folder (if any)
        exiftool_path = raw_cfg.get("exiftool_path") if isinstance(raw_cfg, dict) else None
        # allow configuring exiftool timeout (seconds) via config.json
        try:
            exiftool_timeout = int(raw_cfg.get("exiftool_timeout", exiftool_timeout)) if isinstance(raw_cfg, dict) else exiftool_timeout
        except Exception:
            exiftool_timeout = exiftool_timeout
        # If not present in folder config, try project config next to this package
        if not exiftool_path:
            project_cfg_path = Path(__file__).resolve().parents[1] / "config.json"
            if project_cfg_path.exists():
                try:
                    with project_cfg_path.open("r", encoding="utf-8") as fh:
                        proj_cfg = json.load(fh)
                        exiftool_path = proj_cfg.get("exiftool_path")
                        # allow project-level exiftool_timeout
                        try:
                            exiftool_timeout = int(proj_cfg.get("exiftool_timeout", exiftool_timeout))
                        except Exception:
                            pass
                except Exception:
                    exiftool_path = None
    except Exception:
        exiftool_path = None

    # Build candidate list first so we can report total and progress (memory: holds Path objects)
    candidates = []
    limit = getattr(args, "limit", None)

    # Use optimized filtering logic based on which filters are configured
    # to avoid redundant None checks in the hot loop
    has_ext_filter = exts is not None
    has_min_size = min_size is not None
    has_max_size = max_size is not None

    # Measure time spent discovering and filtering files
    start_time = time.time()
    print(f"Discovering files in {folder}...")

    # Track progress for user visibility
    files_scanned = 0
    last_progress_time = start_time
    progress_interval = 2.0  # Report progress every 2 seconds

    # Remove sorting to avoid collecting all files in memory first - process as we discover them
    for p in _iter_files(folder, recursive):
        files_scanned += 1

        # Show progress every N seconds during discovery
        current_time = time.time()
        if current_time - last_progress_time >= progress_interval:
            elapsed = current_time - start_time
            print(f"  Scanned {files_scanned:,} files, found {len(candidates):,} candidates ({elapsed:.1f}s elapsed)...")
            last_progress_time = current_time

        # extension filter (strict: if exts provided we only consider those)
        if has_ext_filter and p.suffix.lower() not in exts:
            continue
        try:
            size = p.stat().st_size
        except Exception as exc:
            print(f"skipping {p}: cannot stat file: {exc}")
            continue
        # Only check size constraints if they are configured
        if has_min_size and size < min_size:
            continue
        if has_max_size and size > max_size:
            continue
        candidates.append((p, size))
        # Apply limit if specified
        if limit and len(candidates) >= limit:
            break

    discovery_time = time.time() - start_time
    total = len(candidates)
    print(f"Discovery complete: found {total:,} candidate files (scanned {files_scanned:,} total files in {discovery_time:.2f}s)")

    # Worker pool size (tests may not set this arg)
    workers = getattr(args, "workers", None) or 4

    def _hash_worker(item):
        p, size = item
        path_str = str(p)
        try:
            md5 = md5_file(path_str)
        except Exception as exc:
            return {"path": path_str, "size": size, "md5": None, "phash": None, "media_type": None, "error": str(exc)}
        try:
            ph = phash_stub(path_str)
        except Exception:
            ph = None
        # Detect actual file type using magic bytes
        try:
            media_type = detect_media_type(path_str)
        except Exception:
            media_type = None
        return {"path": path_str, "size": size, "md5": md5, "phash": ph, "media_type": media_type, "error": None}

    # Submit hashing work to workers; collect results and write to DB in main thread
    results = []
    if total > 0:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            future_to_item = {ex.submit(_hash_worker, item): item for item in candidates}
            for i, fut in enumerate(concurrent.futures.as_completed(future_to_item), start=1):
                res = fut.result()
                results.append(res)
                path = res.get("path")
                size = res.get("size")
                md5 = res.get("md5")
                ph = res.get("phash")
                media_type = res.get("media_type")
                err = res.get("error")

                # Check if we have folder progress info
                folder_idx = getattr(args, "folder_idx", None)
                total_folders = getattr(args, "total_folders", None)

                if err:
                    if folder_idx and total_folders:
                        print(f"{folder_idx} / {total_folders}: {i} / {total}: skipping {path}: {err}")
                    else:
                        print(f"{i} / {total}: skipping {path}: {err}")
                    continue

                if folder_idx and total_folders:
                    print(f"{folder_idx} / {total_folders}: {i} / {total}: found file: {path} size={size} md5={md5} phash={ph} type={media_type}")
                else:
                    print(f"{i} / {total}: found file: {path} size={size} md5={md5} phash={ph} type={media_type}")
                if repo:
                    try:
                        # If exiftool_path is configured, run it first and capture raw EXIF
                        raw_out = None
                        if exiftool_path:
                            try:
                                import subprocess

                                proc = subprocess.run([exiftool_path, "-j", str(path)], capture_output=True, text=True, timeout=exiftool_timeout)
                                raw_out = proc.stdout if proc.returncode == 0 else None
                            except subprocess.TimeoutExpired as te:
                                print(f"exiftool timed out for {path} after {exiftool_timeout}s: {te}")
                                raw_out = None
                            except Exception as ex_exc:
                                print(f"exiftool invocation failed for {path}: {ex_exc}")
                                raw_out = None

                        created = repo.create_file(
                            path=str(Path(path).resolve()),
                            original_path=str(Path(path).resolve()),
                            name=Path(path).name,
                            original_name=Path(path).name,
                            size=size,
                            md5_hash=md5,
                            photo_hash=ph,
                            media_type=media_type,
                            raw_exif=raw_out,
                        )
                        # Persist raw EXIF to exif_data table
                        if raw_out:
                            repo.save_exif(created.id, raw_out)
                    except Exception as exc:
                        # Per user policy, abort the entire scan if any file
                        # with GPS cannot be reverse-geocoded to a city/country.
                        print(f"FATAL: error persisting {path}: {exc}")
                        raise SystemExit(1)

    return 0


def duplicates(args):
    # Provide a simple duplicates/near-duplicates listing that uses the
    # Repository clustering helper. If run inside tests, a Session may be
    # injected via `args.session` for deterministic behavior. Otherwise this
    # command is a no-op in the scaffold.
    session = getattr(args, "session", None)
    if session is None:
        print("No database session provided; cannot list duplicates in scaffold")
        return 0

    repo = Repository(session)
    threshold = getattr(args, "threshold", 5)
    clusters = repo.cluster_similar_photos(threshold=threshold)
    if not clusters:
        print("No clusters found")
        return 0

    for i, cluster in enumerate(clusters, start=1):
        print(f"Cluster {i} (size={len(cluster)}):")
        for fid in cluster:
            f = repo.get_file_by_id(fid)
            if f:
                print(f"  - {f.path} (id={f.id})")
    return 0


def deduplicate(args):
    """Move duplicate files to a designated folder (wrapper for deduplicate.py script)."""
    print("Please use the standalone script for deduplication:")
    print("  python scripts/deduplicate.py --config config.json [--dry-run] [--folders ...]")
    print("\nFor help:")
    print("  python scripts/deduplicate.py --help")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dupdetector")
    sub = parser.add_subparsers(dest="cmd")

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("folder", nargs="?", default=".")
    p_scan.add_argument("--config", help="Path to JSON config file (default: config.json)")
    # CLI overrides (optional) — when present they override values in config.json
    p_scan.add_argument("--recursive", action="store_true", help="Override config: recurse into subdirectories")
    p_scan.add_argument("--extensions", help="Override config: comma-separated list of file extensions to include (e.g. jpg,png,mp4)")
    p_scan.add_argument("--min-size", type=int, help="Override config: minimum file size in bytes to include")
    p_scan.add_argument("--max-size", type=int, help="Override config: maximum file size in bytes to include")
    p_scan.add_argument("--limit", type=int, help="Limit the number of files to process")
    p_scan.add_argument("--workers", type=int, help="Number of worker threads for hashing")
    p_scan.set_defaults(func=scan)

    p_dup = sub.add_parser("duplicates")
    p_dup.set_defaults(func=duplicates)

    p_dedup = sub.add_parser("deduplicate", help="Move duplicate files to designated folder (see scripts/deduplicate.py)")
    p_dedup.set_defaults(func=deduplicate)

    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return args.func(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
