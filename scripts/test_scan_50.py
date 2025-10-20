import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

# Ensure package import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from dupdetector.lib.database import InMemoryAdapter
from dupdetector.services.repository import Repository
from dupdetector.cli import _iter_files
from dupdetector.lib.hashing import md5_file, phash_stub

import subprocess

ROOT = Path(__file__).resolve().parents[1]
proj_cfg_path = ROOT / 'config.json'
if not proj_cfg_path.exists():
    print('project config.json not found at', proj_cfg_path)
    raise SystemExit(1)

proj_cfg = json.loads(proj_cfg_path.read_text(encoding='utf-8'))
media_folders = proj_cfg.get('media_folders') or []
if not media_folders:
    print('no media_folders configured in project config.json')
    raise SystemExit(1)

folder = Path(media_folders[0])
if not folder.exists():
    print('media folder does not exist:', folder)
    raise SystemExit(1)

exiftool_path = proj_cfg.get('exiftool_path')
exts = proj_cfg.get('extensions')
min_size = proj_cfg.get('min_size')
max_size = proj_cfg.get('max_size')

# Build a package-level config file for dupdetector to pick up geocode settings.
# Parse `geodatabase` URL in project config (if present) into local_geonames settings.
from urllib.parse import urlparse, unquote
geodatabase = proj_cfg.get('geodatabase')
package_cfg = {}
if geodatabase:
    try:
        p = urlparse(geodatabase)
        user = unquote(p.username) if p.username else None
        password = unquote(p.password) if p.password else None
        host = p.hostname
        port = p.port or 3306
        # path often like /geonames
        database = p.path[1:] if p.path and p.path.startswith('/') else p.path
        package_cfg = {
            'geocode': {
                'enabled': True,
                'providers': ['local_geonames'],
                'local_geonames': {
                    'host': host,
                    'user': user,
                    'password': password,
                    'database': database,
                    'port': port,
                }
            }
        }
    except Exception as e:
        print('failed to parse geodatabase url:', e)

# Write package config to src/dupdetector/config.json so repository will pick it up.
pkg_cfg_path = Path(__file__).resolve().parents[1] / 'src' / 'dupdetector' / 'config.json'
try:
    pkg_cfg_path.write_text(json.dumps(package_cfg), encoding='utf-8')
    wrote_pkg_cfg = True
except Exception as e:
    print('failed to write package config:', e)
    wrote_pkg_cfg = False

# Use in-memory DB to avoid touching production DB.
adapter = InMemoryAdapter()
session = adapter.session()
repo = Repository(session)

# Build candidate list (respect extensions and size limits) and take first 50
candidates = []
for p in _iter_files(folder, True):
    if exts is not None and p.suffix.lower().lstrip('.') not in exts:
        continue
    try:
        size = p.stat().st_size
    except Exception:
        continue
    if min_size is not None and size < int(min_size):
        continue
    if max_size is not None and size > int(max_size):
        continue
    candidates.append((p, size))
    if len(candidates) >= 50:
        break

print(f'Will process {len(candidates)} files from {folder}')

processed = 0
for i, (p, size) in enumerate(candidates, start=1):
    path_str = str(p)
    try:
        md5 = md5_file(path_str)
    except Exception as exc:
        print('skip md5 fail', path_str, exc)
        continue
    try:
        ph = phash_stub(path_str)
    except Exception:
        ph = None

    raw_out = None
    if exiftool_path:
        try:
            proc = subprocess.run([exiftool_path, '-j', str(p)], capture_output=True, text=True, timeout=15)
            raw_out = proc.stdout if proc.returncode == 0 else None
        except Exception as ex_exc:
            print('exiftool invocation failed for', p, ex_exc)
            raw_out = None

    try:
        created = repo.create_file(
            path=str(p.resolve()),
            original_path=str(p.resolve()),
            name=p.name,
            original_name=p.name,
            size=size,
            md5_hash=md5,
            photo_hash=ph,
            raw_exif=raw_out,
        )
    except SystemExit:
        print('Scan aborted due to fatal create_file error')
        break
    except Exception as e:
        print('create_file error for', p, e)
        break
    processed += 1
    print(f'[{i}] inserted id={created.id} path={created.path} city={getattr(created, "city", None)} country={getattr(created, "country", None)}')

print('\nSummary of inserted rows:')
for f in repo.list_files(limit=processed):
    print(f'id={f.id} path={f.path} city={getattr(f, "city", None)} country={getattr(f, "country", None)} geocode_provenance={getattr(f, "geocode_provenance", None)}')

# cleanup package config if we wrote it
try:
    if wrote_pkg_cfg and pkg_cfg_path.exists():
        pkg_cfg_path.unlink()
except Exception:
    pass

print('\nDone')
