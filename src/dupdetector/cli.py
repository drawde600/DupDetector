import argparse
from pathlib import Path
from typing import Optional, Iterable, Set, Any
import json

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
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
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

    for p in sorted(_iter_files(folder, recursive)):
        # extension filter
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

        try:
            md5 = md5_file(str(p))
        except Exception as exc:
            print(f"skipping {p}: {exc}")
            continue
        ph = phash_stub(str(p))
        print(f"found file: {p} size={size} md5={md5} phash={ph}")
        if repo:
            repo.create_file(
                path=str(p.resolve()),
                original_path=str(p.resolve()),
                name=p.name,
                original_name=p.name,
                size=size,
                md5_hash=md5,
                photo_hash=ph,
            )

    return 0


def duplicates(args):
    print("Listing duplicates (none in scaffold)")
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
