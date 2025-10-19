import argparse
from pathlib import Path
from typing import Optional, Iterable, Set, Any
import json
import concurrent.futures
import traceback

from dupdetector.lib.hashing import md5_file, phash_stub
from dupdetector.services.repository import Repository


def _iter_files(folder: Path, recursive: bool) -> Iterable[Path]:
    if recursive:
        for p in folder.rglob("*"):
            if p.is_file():
                yield p
    else:
        for p in folder.iterdir():
            if p.is_file():
                yield p


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



def _load_config(path: str) -> dict[str, Any]:
    p = Path(path)
    # Provide clear visibility for which config paths are being consulted and
    # the exact contents (line-by-line) read from the file.
    try:
        if not p.exists():
            print(f"_load_config: path does not exist: {p}")
            return {}
        print(f"_load_config: attempting to load config from: {p}")
        # Read file as text and print lines with numbers for full visibility
        try:
            with p.open("r", encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except Exception as e:
            print(f"_load_config: failed to read file lines from {p}: {e}")
            traceback.print_exc()
            return {}

        print(f"_load_config: file {p} contents ({len(lines)} lines):")
        for i, ln in enumerate(lines, start=1):
            # print with line numbers to help debugging of config parsing issues
            print(f"{p}:{i}: {ln}")

        # Now parse JSON
        try:
            data = json.loads("\n".join(lines))
            print(f"_load_config: parsed JSON config from: {p}")
            return data
        except Exception as e:
            print(f"_load_config: failed to parse JSON from {p}: {e}")
            traceback.print_exc()
            return {}
    except Exception as e:
        print(f"_load_config: unexpected error when loading {p}: {e}")
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
    raw_cfg = _load_config(cfg_path) if cfg_path else {}
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
    min_size = getattr(args, "min_size", None) if getattr(args, "min_size", None) is not None else cfg.get("min_size")
    max_size = getattr(args, "max_size", None) if getattr(args, "max_size", None) is not None else cfg.get("max_size")

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
    for p in sorted(_iter_files(folder, recursive)):
        # extension filter (strict: if exts provided we only consider those)
        if exts is not None and p.suffix.lower() not in exts:
            continue
        try:
            size = p.stat().st_size
        except Exception as exc:
            print(f"skipping {p}: cannot stat file: {exc}")
            continue
        if min_size is not None and size < int(min_size):
            continue
        if max_size is not None and size > int(max_size):
            continue
        candidates.append((p, size))
        # Apply limit if specified
        if limit and len(candidates) >= limit:
            break

    total = len(candidates)
    print(f"Found {total} candidate files to process{' (limit reached)' if limit and len(candidates) >= limit else ''}")

    # Worker pool size (tests may not set this arg)
    workers = getattr(args, "workers", None) or 4

    def _hash_worker(item):
        p, size = item
        path_str = str(p)
        try:
            md5 = md5_file(path_str)
        except Exception as exc:
            return {"path": path_str, "size": size, "md5": None, "phash": None, "error": str(exc)}
        try:
            ph = phash_stub(path_str)
        except Exception:
            ph = None
        return {"path": path_str, "size": size, "md5": md5, "phash": ph, "error": None}

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
                err = res.get("error")
                if err:
                    print(f"{i} / {total}: skipping {path}: {err}")
                    continue
                print(f"{i} / {total}: found file: {path} size={size} md5={md5} phash={ph}")
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
                            raw_exif=raw_out,
                        )
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

    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return args.func(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
