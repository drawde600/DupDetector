from typing import Iterable, Optional
import threading
import json
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func as sa_func
from sqlalchemy.orm import Session

from dupdetector.models.file import File
from dupdetector.models.tag import Tag
# Module-level cached geocode config to avoid reading config file per file
_geocode_cfg_cache = None
_geocode_cfg_lock = threading.Lock()

def _get_geocode_cfg_cached():
    """Load geocode config once and cache it.

    Returns the `geocode` dict from either the CWD `config.json` or the
    package `config.json`, or None if not present. Prints a single-line
    diagnostic indicating where (if anywhere) a geocode block was found.
    """
    global _geocode_cfg_cache
    if _geocode_cfg_cache is not None:
        return _geocode_cfg_cache
    with _geocode_cfg_lock:
        if _geocode_cfg_cache is not None:
            return _geocode_cfg_cache
        # Helper to convert a legacy top-level `geodatabase` DSN into a
        # `geocode` block using local_geonames provider so older configs
        # continue to work without editing.
        def _convert_legacy_geodatabase(proj):
            try:
                dsn = proj.get('geodatabase')
                if not dsn or not isinstance(dsn, str):
                    return None
                from urllib.parse import urlparse, unquote
                u = urlparse(dsn)
                user = u.username
                passwd = u.password
                host = u.hostname
                port = u.port or 3306
                db = (u.path[1:]) if u.path and u.path.startswith('/') else u.path
                if not (host and user and db):
                    return None
                return {
                    'enabled': True,
                    'providers': ['local_geonames'],
                    'local_geonames': {
                        'host': host,
                        'user': user,
                        'password': unquote(passwd) if passwd else None,
                        'database': db,
                        'port': port,
                    }
                }
            except Exception:
                return None

        # Try CWD config first
        try:
            cfg_path = Path.cwd() / "config.json"
            if cfg_path.exists():
                try:
                    with cfg_path.open("r", encoding="utf-8") as fh:
                        proj = json.load(fh)
                        _geocode_cfg_cache = proj.get("geocode")
                        if not _geocode_cfg_cache:
                            # try legacy top-level geodatabase
                            legacy = _convert_legacy_geodatabase(proj)
                            if legacy:
                                _geocode_cfg_cache = legacy
                                print(f"geocode: derived geocode block from legacy geodatabase in cwd config: {cfg_path}")
                                return _geocode_cfg_cache
                        if _geocode_cfg_cache:
                            print(f"geocode: found geocode block in cwd config: {cfg_path}")
                        else:
                            print(f"geocode: no geocode block in cwd config: {cfg_path}")
                        return _geocode_cfg_cache
                except Exception as e:
                    print(f"geocode: failed parsing cwd config {cfg_path}: {e}")
        except Exception:
            print("geocode: unexpected error checking cwd config path")

        # Try package config path next
        try:
            pkg_cfg_path = Path(__file__).resolve().parents[1] / "config.json"
            if pkg_cfg_path.exists():
                try:
                    with pkg_cfg_path.open("r", encoding="utf-8") as fh:
                        proj = json.load(fh)
                        _geocode_cfg_cache = proj.get("geocode")
                        if _geocode_cfg_cache:
                            print(f"geocode: found geocode block in package config: {pkg_cfg_path}")
                        else:
                            print(f"geocode: no geocode block in package config: {pkg_cfg_path}")
                        return _geocode_cfg_cache
                except Exception as e:
                    print(f"geocode: failed parsing package config {pkg_cfg_path}: {e}")
        except Exception:
            print("geocode: unexpected error checking package config path")

        print("geocode: no geocode configuration found in cwd or package config")
        _geocode_cfg_cache = None
        return None


class Repository:
    """Small repository/service layer wrapping SQLAlchemy session operations.

    Accepts a Session instance (or session factory) and provides simple CRUD
    helpers used by higher-level code and tests.
    """

    def __init__(self, session: Session):
        self.session = session

    # File helpers
    def create_file(self, **kwargs) -> File:
        # duplicate detection: if md5_hash exists, mark as duplicate of first found
        md5 = kwargs.get("md5_hash")
        photo_hash = kwargs.get("photo_hash")
        duplicate_of = None
        if md5:
            existing = self.session.query(File).filter_by(md5_hash=md5).first()
            if existing:
                duplicate_of = existing.id
        if duplicate_of is None and photo_hash:
            existing = self.session.query(File).filter_by(photo_hash=photo_hash).first()
            if existing:
                duplicate_of = existing.id

        # allow callers to pass raw_exif so we can apply EXIF-derived values
        raw_exif = kwargs.pop("raw_exif", None)

        f = File(**kwargs)
        # If raw_exif provided, attempt to parse and apply before commit so a
        # single insert populates derived fields (gps, city, country, taken_at).
        if raw_exif:
            try:
                # reuse parsing logic from update_file_from_exif via helper
                parsed = None
                try:
                    import json as _json
                    parsed_list = _json.loads(raw_exif)
                    if isinstance(parsed_list, list) and parsed_list:
                        parsed = parsed_list[0]
                    elif isinstance(parsed_list, dict):
                        parsed = parsed_list
                except Exception:
                    parsed = None
                if parsed:
                    # Apply parsed EXIF to the in-memory File object.
                    # Do not swallow exceptions here: per project policy a GPS
                    # value that cannot be reverse-geocoded to city+country
                    # must abort the scan. Let any parsing/geocode exceptions
                    # propagate to the caller so the scan can fail fast.
                    self._apply_parsed_exif_to_file(f, parsed)
            except Exception:
                pass
        if duplicate_of is not None:
            f.is_duplicate = True
            f.duplicate_of_id = duplicate_of

        self.session.add(f)
        try:
            self.session.commit()
        except IntegrityError:
            # Session is in a broken state; rollback to continue using it.
            self.session.rollback()
            # Try to find an existing record that caused the unique constraint.
            # Prefer matching by path if provided, otherwise fall back to md5/photo_hash.
            path = kwargs.get("path")
            md5 = kwargs.get("md5_hash")
            photo_hash = kwargs.get("photo_hash")
            existing = None
            if path:
                existing = self.session.query(File).filter_by(path=path).first()
            if existing is None and md5:
                existing = self.session.query(File).filter_by(md5_hash=md5).first()
            if existing is None and photo_hash:
                existing = self.session.query(File).filter_by(photo_hash=photo_hash).first()
            if existing:
                # Mark the object as duplicate (idempotent) and update timestamp.
                existing.is_duplicate = True
                # Use a DB-side update to set updated_at using the same server
                # timestamp mechanism as the original insert (func.current_timestamp()).
                # This avoids timezone/clock mismatches between Python and DB server.
                try:
                    (self.session.query(File)
                        .filter_by(id=existing.id)
                        .update({"is_duplicate": True, "updated_at": sa_func.current_timestamp()}, synchronize_session=False))
                    self.session.commit()
                    # Refresh to load DB-managed values
                    self.session.refresh(existing)
                except Exception:
                    # If the DB-side update fails for some reason, rollback and
                    # fall back to attaching the existing object to the session.
                    self.session.rollback()
                    self.session.add(existing)
                    self.session.commit()
                    self.session.refresh(existing)
                return existing
            # If we couldn't find an existing record, re-raise so caller can investigate
            raise
        # refresh to populate defaults
        self.session.refresh(f)
        return f

    def get_file_by_id(self, file_id: int) -> Optional[File]:
        # use Session.get to avoid legacy Query.get warnings
        return self.session.get(File, file_id)

    def get_files_by_md5(self, md5: str) -> list[File]:
        return self.session.query(File).filter_by(md5_hash=md5).all()

    def list_files(self, limit: Optional[int] = None) -> list[File]:
        q = self.session.query(File).order_by(File.id)
        if limit:
            q = q.limit(limit)
        return q.all()

    def delete_file(self, file_id: int) -> bool:
        f = self.get_file_by_id(file_id)
        if not f:
            return False
        self.session.delete(f)
        self.session.commit()
        return True

    # Tag helpers (small convenience)
    def create_tag(self, name: str) -> Tag:
        t = Tag(name=name)
        self.session.add(t)
        self.session.commit()
        self.session.refresh(t)
        return t

    def list_tags(self) -> list[Tag]:
        return self.session.query(Tag).order_by(Tag.name).all()

    # Near-duplicate helpers (photo_hash)
    def find_similar_by_phash(self, phash: str, max_distance: int = 5) -> list[File]:
        """Return files whose photo_hash Hamming distance to `phash` is <= max_distance.

        This implementation fetches candidates with non-null photo_hash and computes
        Hamming distances in Python (sufficient for small datasets / tests).
        """
        from dupdetector.lib.hashing import hamming_distance

        candidates = self.session.query(File).filter(File.photo_hash.isnot(None)).all()
        similar = []
        for c in candidates:
            try:
                dist = hamming_distance(phash, c.photo_hash)
            except Exception:
                continue
            if dist <= max_distance:
                similar.append(c)
        return similar

    def cluster_similar_photos(self, threshold: int = 5) -> list[list[int]]:
        """Cluster files by photo_hash using a Hamming distance threshold.

        Returns list of clusters containing file IDs.
        """
        from dupdetector.lib.hashing import cluster_by_hamming

        rows = self.session.query(File.id, File.photo_hash).filter(File.photo_hash.isnot(None)).all()
        # rows are tuples (id, phash)
        clusters = cluster_by_hamming(rows, threshold)
        return clusters

    # Minimal predecessor/linking helpers
    def find_predecessor_for(self, new_file: File) -> Optional[int]:
        """Try to find a likely predecessor file id for a newly created file.

        Heuristics (in priority):
        - content_identifier matches an existing file
        - photo_identifier matches
        - same path but different md5 (latest)
        Returns an existing file id or None.
        """
        # content_identifier
        if getattr(new_file, 'content_identifier', None):
            row = (self.session.query(File.id)
                   .filter(File.content_identifier == new_file.content_identifier)
                   .filter(File.id != new_file.id)
                   .order_by(File.id.desc())
                   .first())
            if row:
                return row[0]
        # photo_identifier
        if getattr(new_file, 'photo_identifier', None):
            row = (self.session.query(File.id)
                   .filter(File.photo_identifier == new_file.photo_identifier)
                   .filter(File.id != new_file.id)
                   .order_by(File.id.desc())
                   .first())
            if row:
                return row[0]
        # same path but different md5
        try:
            if getattr(new_file, 'path', None):
                row = (self.session.query(File.id)
                       .filter(File.path == new_file.path)
                       .filter(File.id != new_file.id)
                       .filter(File.md5_hash != new_file.md5_hash)
                       .order_by(File.id.desc())
                       .first())
                if row:
                    return row[0]
        except Exception as _e:
            try:
                import traceback as _tb
                print('geocode: unexpected error in geocode block:', _e)
                print(_tb.format_exc())
            except Exception:
                # if printing fails, re-raise to avoid hiding the original error
                raise
        return None

    def link_previous(self, new_id: int, previous_id: int) -> None:
        """Set previous_id on a file record."""
        try:
            (self.session.query(File)
                .filter_by(id=new_id)
                .update({'previous_id': previous_id, 'updated_at': sa_func.current_timestamp()}, synchronize_session=False))
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def inherit_manual_metadata(self, new_id: int, from_id: Optional[int] = None, force: bool = False) -> Optional[File]:
        """Copy manual metadata from `from_id` (or new.previous_id/heuristic) to new file.

        Only copies fields when the source row indicates manual provenance
        (geocode_provenance in (2,4) and/or taken_at_provenance == 2), unless
        `force` is True.
        """
        new = self.get_file_by_id(new_id)
        if not new:
            return None
        if from_id is None:
            from_id = getattr(new, 'previous_id', None)
        if from_id is None:
            candidate = self.find_predecessor_for(new)
            from_id = candidate
        if from_id is None:
            return new
        old = self.get_file_by_id(from_id)
        if not old:
            return new

        copied = False
        # Copy manual geocode if source indicates manual (2 or 4) or force
        try:
            if force or (old.geocode_provenance in (2, 4)):
                new.gps = old.gps
                new.city = old.city
                new.country = old.country
                new.geocode_provenance = old.geocode_provenance
                copied = True
        except Exception:
            pass

        # Copy manual taken_at
        try:
            if force or (old.taken_at_provenance == 2):
                new.taken_at = old.taken_at
                new.taken_at_provenance = old.taken_at_provenance
                copied = True
        except Exception:
            pass

        if copied:
            try:
                self.session.commit()
                self.session.refresh(new)
            except Exception:
                self.session.rollback()
                raise

        return new

    # Exif helpers
    def save_exif(self, file_id: int, raw_exif: str) -> None:
        """Save or replace the raw exif dump for a given file_id."""
        from dupdetector.models.exif import ExifData

        # If an ExifData row already exists for this file, update it; otherwise insert.
        existing = self.session.query(ExifData).filter_by(file_id=file_id).first()
        if existing:
            existing.raw_exif = raw_exif
            try:
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
            self.session.refresh(existing)
            return

        row = ExifData(file_id=file_id, raw_exif=raw_exif)
        self.session.add(row)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def get_exif_by_file_id(self, file_id: int) -> Optional[str]:
        from dupdetector.models.exif import ExifData

        row = self.session.query(ExifData).filter_by(file_id=file_id).first()
        return row.raw_exif if row else None

    def _apply_parsed_exif_to_file(self, f: File, data: dict) -> None:
        """Apply parsed exif dict to an in-memory File object (no commit).

        This consolidates the parsing logic so it can be used both on create
        (single-insert path) and update paths. When GPS is present this will
        attempt reverse-geocoding using configured providers and will ensure
        `city` and `country` are set (see user policy: must have values).
        """
        changed = False

        # Manufacturer
        make = data.get("Make") or data.get("Manufacturer") or data.get("Maker")
        if make and getattr(f, "manufacturer", None) != make:
            f.manufacturer = str(make)
            changed = True

        # taken_at
        def _parse_exif_date(val: str):
            from datetime import datetime

            if not val or not isinstance(val, str):
                return None
            s = val.strip()
            try:
                if len(s) >= 19 and s[4] == ':' and s[7] == ':':
                    s2 = s.replace(':', '-', 2).replace(' ', 'T', 1)
                    return datetime.fromisoformat(s2)
            except Exception:
                pass
            try:
                s2 = s.replace(' ', 'T')
                return datetime.fromisoformat(s2)
            except Exception:
                pass
            try:
                from datetime import datetime as _dt
                return _dt.strptime(s, "%Y:%m:%d %H:%M:%S")
            except Exception:
                try:
                    return _dt.strptime(s, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    return None

        date_candidates = [
            "DateTimeOriginal", "CreateDate", "DateCreated", "OriginDate",
            "DateTime", "ModifyDate", "FileModifyDate", "Date/Time Original",
            "Date Time Original",
        ]
        taken = None
        for tag in date_candidates:
            if tag in data and data[tag]:
                dt = _parse_exif_date(data[tag])
                if dt:
                    taken = dt
                    break
        if taken and getattr(f, "taken_at", None) != taken:
            f.taken_at = taken
            f.taken_at_provenance = 1
            changed = True

        # Identifiers
        def _pick_tag(dct, candidates):
            for k in candidates:
                if k in dct and dct[k]:
                    return dct[k]
            return None

        content_id = _pick_tag(data, ["ContentIdentifier", "Content Identifier", "ContentID", "Content Id"]) 
        photo_id = _pick_tag(data, ["Photo Identifier", "PhotoIdentifier", "PhotoIdentifierGUID", "Photo ID", "PhotoID"]) 
        if content_id and getattr(f, "content_identifier", None) != content_id:
            f.content_identifier = str(content_id)
            changed = True
        if photo_id and getattr(f, "photo_identifier", None) != photo_id:
            f.photo_identifier = str(photo_id)
            changed = True

        # Dimensions
        w = data.get("ExifImageWidth") or data.get("ImageWidth") or data.get("Image Width")
        h = data.get("ExifImageHeight") or data.get("ImageHeight") or data.get("Image Height")
        if w and h:
            try:
                dim = f"{int(w)}x{int(h)}"
            except Exception:
                dim = f"{w}x{h}"
            if getattr(f, "dimensions", None) != dim:
                f.dimensions = dim
                changed = True

        # GPS parse and set
        lat = data.get("GPSLatitude")
        lon = data.get("GPSLongitude")
        if lat and lon:
            gps = f"{lat},{lon}"
            if getattr(f, "gps", None) != gps:
                f.gps = str(gps)
                changed = True

            # Reverse-geocode (must produce city+country when GPS present)
            # Use cached geocode loader to avoid reading config and printing
            # the same diagnostics for every file.
            geocode_cfg = _get_geocode_cfg_cached()

            # If GPS exists but we have no geocode configuration, fail fast per policy
            if not geocode_cfg or not geocode_cfg.get('enabled'):
                raise RuntimeError(
                    "geocode configuration not found or disabled; cannot reverse-geocode GPS coordinates"
                )

            # Helper: parse DMS into decimal degrees
            def _parse_dms(v: str):
                s = str(v).strip()
                if s.replace('.', '').replace('-', '').isdigit():
                    return float(s)
                dirc = None
                if s.endswith(('N', 'S', 'E', 'W')):
                    dirc = s[-1]
                    s = s[:-1].strip()
                for ch in ("deg", "°"):
                    s = s.replace(ch, ' ')
                s = s.replace('"', ' ').replace("'", ' ')
                parts = [p for p in s.split() if p]
                if len(parts) >= 3:
                    deg = float(parts[0])
                    minu = float(parts[1])
                    sec = float(parts[2])
                    val = deg + (minu / 60.0) + (sec / 3600.0)
                elif len(parts) == 2:
                    deg = float(parts[0])
                    minu = float(parts[1])
                    val = deg + (minu / 60.0)
                else:
                    val = float(parts[0])
                if dirc and dirc in ('S', 'W'):
                    val = -abs(val)
                return val

            try:
                lat_f = _parse_dms(lat)
            except Exception:
                lat_f = float(lat)
            try:
                lon_f = _parse_dms(lon)
            except Exception:
                lon_f = float(lon)

            # Try providers in order; require city+country if GPS present
            city = None
            country = None
            tried = []
            providers = []
            if geocode_cfg and geocode_cfg.get('enabled'):
                providers = list(geocode_cfg.get('providers') or [])

            # Always try local geonames first if configured
            for prov in providers:
                try:
                    pv = str(prov).lower()
                except Exception:
                    continue
                tried.append(pv)
                if pv == 'local_geonames':
                    gn = geocode_cfg.get('local_geonames', {})
                    host = gn.get('host')
                    user = gn.get('user')
                    db = gn.get('database')
                    port = int(gn.get('port', 3306)) if gn.get('port') else 3306
                    passwd = gn.get('password')
                    if not (host and user and db):
                        continue
                    try:
                        import pymysql
                        conn = pymysql.connect(host=host, port=port, user=user, password=passwd, database=db, connect_timeout=5)
                        cur = conn.cursor()
                        sql = ("SELECT name, country_code, latitude, longitude, "
                               "(6371 * 2 * ASIN(SQRT(POWER(SIN(RADIANS(latitude - %s) / 2), 2) "
                               "+ COS(RADIANS(%s)) * COS(RADIANS(latitude)) * POWER(SIN(RADIANS(longitude - %s) / 2), 2)))) "
                               "AS distance_km FROM geoname ORDER BY distance_km ASC LIMIT 10;")
                        try:
                            cur.execute(sql, (lat_f, lat_f, lon_f))
                            rows = cur.fetchall()
                        except Exception:
                            rows = []
                        finally:
                            try:
                                cur.close()
                            except Exception:
                                pass
                            try:
                                conn.close()
                            except Exception:
                                pass
                        # pick nearest
                        best = None
                        best_d = None
                        for r in rows:
                            try:
                                if len(r) >= 4:
                                    pname = r[0]
                                    pcountry = r[1]
                                    plat = float(r[2])
                                    plon = float(r[3])
                                else:
                                    continue
                                from math import radians, sin, cos, sqrt, atan2
                                def _haversine(lat1, lon1, lat2, lon2):
                                    R = 6371.0
                                    dlat = radians(lat2 - lat1)
                                    dlon = radians(lon2 - lon1)
                                    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
                                    c = 2 * atan2(sqrt(a), sqrt(1 - a))
                                    return R * c
                                d = _haversine(lat_f, lon_f, plat, plon)
                            except Exception:
                                continue
                            if best is None or d < best_d:
                                best = (pname, pcountry)
                                best_d = d
                        if best:
                            city, country = best[0], best[1]
                            break
                    except Exception:
                        continue
                elif pv == 'geonames':
                    try:
                        import requests
                        gn_cfg = geocode_cfg.get('geonames', {})
                        username = gn_cfg.get('username')
                        if not username:
                            continue
                        resp = requests.get('http://api.geonames.org/findNearbyPlaceNameJSON', params={'lat': str(lat_f), 'lng': str(lon_f), 'username': username}, timeout=6)
                        if resp.status_code == 200:
                            j = resp.json()
                            geonames = j.get('geonames') or []
                            if geonames:
                                p = geonames[0]
                                city = p.get('name')
                                country = p.get('countryName')
                                break
                    except Exception:
                        continue
                elif pv == 'nominatim':
                    try:
                        import requests
                        endpoint = geocode_cfg.get('endpoint') or 'https://nominatim.openstreetmap.org/reverse'
                        params = {'format': 'jsonv2', 'lat': str(lat_f), 'lon': str(lon_f), 'zoom': 10, 'addressdetails': 1}
                        resp = requests.get(endpoint, params=params, timeout=10, headers={'User-Agent': 'DupDetector/1.0'})
                        if resp.status_code == 200:
                            j = resp.json()
                            addr = j.get('address') or {}
                            country = addr.get('country') or addr.get('country_name')
                            city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('municipality')
                            if country or city:
                                break
                    except Exception:
                        continue

            # After trying providers, enforce a value per user requirement
            # If we couldn't resolve a city or country for GPS, raise so
            # the caller (scan) can abort the whole operation per policy.
            if not country or not city:
                raise RuntimeError(f"reverse-geocode failed for GPS {lat_f},{lon_f} (providers tried: {tried})")
            if getattr(f, 'country', None) != country:
                f.country = country
                changed = True
            if getattr(f, 'city', None) != city:
                f.city = city
                changed = True
            # set provenance: 1 = EXIF gps + auto city/country
            try:
                f.geocode_provenance = 1
            except Exception:
                pass
            except Exception:
                # Bubble up geocode/unexpected errors to the caller so the
                # scan can abort. Re-raise the original exception.
                raise

        return changed


    def update_file_from_exif(self, file_id: int) -> Optional[File]:
        """Parse the saved exif JSON for `file_id` and populate File fields.

    This updates manufacturer, dimensions, gps, media_type and taken_at
        when corresponding tags are present in the exif dump. Returns the
        updated File object (or None if the file doesn't exist).
        """
        import json as _json
        from dupdetector.models.exif import ExifData

        f = self.get_file_by_id(file_id)
        if not f:
            return None

        exif_row = self.session.query(ExifData).filter_by(file_id=file_id).first()
        if not exif_row or not exif_row.raw_exif:
            return f

        # exiftool -j output is typically a JSON array with one element per file
        try:
            parsed = _json.loads(exif_row.raw_exif)
        except Exception:
            # Keep original if parsing fails
            return f

        data = None
        if isinstance(parsed, list):
            if len(parsed) > 0 and isinstance(parsed[0], dict):
                data = parsed[0]
        elif isinstance(parsed, dict):
            data = parsed

        if not data:
            return f

        changed = False

        # Manufacturer / Make
        make = data.get("Make") or data.get("Manufacturer") or data.get("Maker")
        if make and (getattr(f, "manufacturer", None) != make):
            f.manufacturer = str(make)
            changed = True

        # Photo taken date: look for common EXIF date tags and parse into datetime
        def _parse_exif_date(val: str):
            from datetime import datetime

            if not val or not isinstance(val, str):
                return None
            s = val.strip()
            # exiftool common format: 'YYYY:MM:DD HH:MM:SS'
            try:
                if len(s) >= 19 and s[4] == ':' and s[7] == ':':
                    # replace first two ':' with '-' to make ISO-like date
                    s2 = s.replace(':', '-', 2).replace(' ', 'T', 1)
                    return datetime.fromisoformat(s2)
            except Exception:
                pass
            # ISO-like formats or 'YYYY-MM-DD HH:MM:SS'
            try:
                s2 = s.replace(' ', 'T')
                return datetime.fromisoformat(s2)
            except Exception:
                pass
            # fallback: try to parse common variants
            try:
                # try without timezone
                return datetime.strptime(s, "%Y:%m:%d %H:%M:%S")
            except Exception:
                try:
                    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    return None

        # check multiple possible date tags
        date_candidates = [
            "DateTimeOriginal",
            "CreateDate",
            "DateCreated",
            "OriginDate",
            "DateTime",
            "ModifyDate",
            "FileModifyDate",
            "Date/Time Original",
            "Date Time Original",
        ]
        taken = None
        for tag in date_candidates:
            if tag in data and data[tag]:
                dt = _parse_exif_date(data[tag])
                if dt:
                    taken = dt
                    break
        if taken and getattr(f, "taken_at", None) != taken:
            f.taken_at = taken
            changed = True
            try:
                # Mark that taken_at was sourced from EXIF
                f.taken_at_provenance = 1
            except Exception:
                pass

        # ContentIdentifier / Photo Identifier (various tag names may be used);
        # prefer ContentIdentifier for grouping related media (photos/mov files)
        def _pick_tag(dct, candidates):
            for k in candidates:
                if k in dct and dct[k]:
                    return dct[k]
            return None

        content_id = _pick_tag(data, ["ContentIdentifier", "Content Identifier", "ContentID", "Content Id"]) 
        photo_id = _pick_tag(data, ["Photo Identifier", "PhotoIdentifier", "PhotoIdentifierGUID", "Photo ID", "PhotoID"]) 
        if content_id and getattr(f, "content_identifier", None) != content_id:
            f.content_identifier = str(content_id)
            changed = True
        if photo_id and getattr(f, "photo_identifier", None) != photo_id:
            f.photo_identifier = str(photo_id)
            changed = True

        # Dimensions: prefer ExifImageWidth/Height or ImageWidth/ImageHeight
        w = data.get("ExifImageWidth") or data.get("ImageWidth") or data.get("Image Width")
        h = data.get("ExifImageHeight") or data.get("ImageHeight") or data.get("Image Height")
        if w and h:
            try:
                dim = f"{int(w)}x{int(h)}"
            except Exception:
                dim = f"{w}x{h}"
            if getattr(f, "dimensions", None) != dim:
                f.dimensions = dim
                changed = True

        # GPS: store as simple lat,lon string when both present
        lat = data.get("GPSLatitude")
        lon = data.get("GPSLongitude")
        if lat and lon:
            gps = f"{lat},{lon}"
            # log GPS read along with any current country/city values
            try:
                cur_country = getattr(f, "country", None)
                cur_city = getattr(f, "city", None)
                print(f"read GPS for file id={f.id}: {gps} (current country={cur_country!r}, city={cur_city!r})")
            except Exception:
                pass
            if getattr(f, "gps", None) != gps:
                f.gps = str(gps)
                changed = True

        # Optional reverse-geocoding: populate city/country when enabled in config
        try:
            import json as _json
            from pathlib import Path as _Path
            cfg_path = _Path.cwd() / "config.json"
            geocode_cfg = None
            if cfg_path.exists():
                try:
                    with cfg_path.open("r", encoding="utf-8") as _fh:
                        proj = _json.load(_fh)
                        geocode_cfg = proj.get("geocode")
                except Exception:
                    geocode_cfg = None
            # fallback to project package config
            if not geocode_cfg:
                try:
                    pkg_cfg_path = _Path(__file__).resolve().parents[1] / "config.json"
                    if pkg_cfg_path.exists():
                        with pkg_cfg_path.open("r", encoding="utf-8") as _fh:
                            proj = _json.load(_fh)
                            geocode_cfg = proj.get("geocode")
                except Exception:
                    geocode_cfg = None
            if geocode_cfg and geocode_cfg.get("enabled") and lat and lon:
                    try:
                        print(f"geocode: entering geocode block for file id={f.id}, raw lat={lat!r}, raw lon={lon!r}")
                        print(f"geocode_cfg providers: {geocode_cfg.get('providers')}")
                    except Exception:
                        pass
                    threshold_km = float(geocode_cfg.get("distance_km", 1.0))
                    lat_f = float(lat)
                    lon_f = float(lon)
                    # If GPS values are in DMS text format (e.g. "14 deg 37' 10.97" N"),
                    # attempt to parse into decimal degrees.
                    def _parse_dms(v: str):
                        # common exiftool DMS formats include: "14 deg 37' 10.97\" N"
                        try:
                            s = str(v).strip()
                            # quick path: if it already looks like a decimal number
                            if s.replace('.', '').replace('-', '').isdigit():
                                return float(s)
                            # split compass direction
                            dir = None
                            if s.endswith(('N', 'S', 'E', 'W')):
                                dir = s[-1]
                                s = s[:-1].strip()
                            # replace degree/min/sec words/symbols with separators
                            for ch in ("deg", "°"):
                                s = s.replace(ch, ' ')
                            s = s.replace("\"", ' ').replace("'", ' ')
                            parts = [p for p in s.split() if p]
                            if len(parts) >= 3:
                                deg = float(parts[0])
                                minu = float(parts[1])
                                sec = float(parts[2])
                                val = deg + (minu / 60.0) + (sec / 3600.0)
                            elif len(parts) == 2:
                                deg = float(parts[0])
                                minu = float(parts[1])
                                val = deg + (minu / 60.0)
                            else:
                                val = float(parts[0])
                            if dir and dir in ('S', 'W'):
                                val = -abs(val)
                            return val
                        except Exception:
                            # fallback to raising so outer code can handle
                            raise

                    try:
                        lat_f = _parse_dms(lat)
                    except Exception:
                        lat_f = float(lat)
                    try:
                        lon_f = _parse_dms(lon)
                    except Exception:
                        lon_f = float(lon)
                    # bounding box delta in degrees (approx)
                    # User requested removing the distance threshold: we still need
                    # a bounding box to limit candidates for performance. Use a
                    # larger default search radius (100 km) so the nearest place
                    # will be found even if it's farther than the old threshold.
                    search_km = float(geocode_cfg.get('search_km', 100.0))
                    delta_deg = max(0.01, search_km / 111.0)
                    # No cache: try providers in order directly
                    # helper: haversine distance
                    from math import radians, sin, cos, sqrt, atan2
                    def _haversine_km(lat1, lon1, lat2, lon2):
                        R = 6371.0
                        dlat = radians(lat2 - lat1)
                        dlon = radians(lon2 - lon1)
                        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
                        c = 2 * atan2(sqrt(a), sqrt(1 - a))
                        return R * c

                    import requests
                    import time

                    providers = geocode_cfg.get("providers") or ([geocode_cfg.get("provider")] if geocode_cfg.get("provider") else [])
                    try:
                        # diagnostic: reveal providers object shape and length
                        try:
                            # force evaluation in case providers is a generator-like object
                            providers_list = list(providers)
                            print(f"geocode: providers forced list={providers_list!r} type={type(providers_list)} len={len(providers_list)}")
                        except Exception:
                            print(f"geocode: providers repr failed, type={type(providers)} repr={repr(providers)}")
                            providers_list = None
                    except Exception:
                        providers_list = None
                    if not providers_list:
                        try:
                            print(f"geocode: providers resolved to empty/falsey, skipping providers loop for file id={f.id}")
                        except Exception:
                            pass
                    # iterate over the forced list when available
                    iter_providers = providers_list if providers_list is not None else providers
                    
                    success = False
                    country = None
                    city = None
                    for prov in iter_providers:
                        # print raw provider so we can see the actual value/shape
                        try:
                            print(f"geocode: provider raw value repr={repr(prov)} type={type(prov)}")
                        except Exception:
                            pass
                        try:
                            prov = str(prov).lower()
                        except Exception:
                            # skip invalid provider entries
                            continue
                        try:
                            # provider attempt log
                            try:
                                print(f"geocode: trying provider {prov} for file id={f.id}")
                            except Exception:
                                pass
                            if prov == "local_geonames":
                                # Query a local geonames MySQL database for nearby places
                                gn_cfg = geocode_cfg.get("local_geonames", {})
                                host = gn_cfg.get("host")
                                port = int(gn_cfg.get("port", 3306))
                                user = gn_cfg.get("user")
                                password = gn_cfg.get("password")
                                database = gn_cfg.get("database")
                                if not (host and user and database):
                                    try:
                                        print("geocode: local_geonames config incomplete, skipping")
                                    except Exception:
                                        pass
                                    continue
                                try:
                                    import pymysql

                                    conn = pymysql.connect(host=host, port=port, user=user, password=password, database=database, connect_timeout=5)
                                    cur = conn.cursor()
                                    # Compute distance in SQL and return the nearest candidates globally
                                    sql = ("SELECT geonameid, name, country_code, latitude, longitude, "
                                           "(6371 * 2 * ASIN(SQRT(POWER(SIN(RADIANS(latitude - %s) / 2), 2) "
                                           "+ COS(RADIANS(%s)) * COS(RADIANS(latitude)) * POWER(SIN(RADIANS(longitude - %s) / 2), 2)))) "
                                           "AS distance_km "
                                           "FROM geoname "
                                           "ORDER BY distance_km ASC "
                                           "LIMIT 10;")
                                    try:
                                        cur.execute(sql, (lat_f, lat_f, lon_f))
                                        rows_g = cur.fetchall()
                                        try:
                                            print(f"geocode: local_geonames returned {len(rows_g)} rows")
                                        except Exception:
                                            pass
                                    except Exception as _e:
                                        try:
                                            print(f"geocode: local_geonames SQL error: {_e}")
                                        except Exception:
                                            pass
                                        rows_g = []
                                    finally:
                                        try:
                                            cur.close()
                                        except Exception:
                                            pass
                                        try:
                                            conn.close()
                                        except Exception:
                                            pass
                                except Exception as e:
                                    # if local DB unavailable or auth fails, log and try next provider
                                    try:
                                        import traceback as _tb
                                        print(f"geocode: local_geonames connection error: {e}")
                                        print(_tb.format_exc())
                                    except Exception:
                                        pass
                                    continue
                                # compute closest candidate via haversine
                                best = None
                                best_d = None
                                for r in rows_g:
                                    try:
                                        # r expected: (geonameid, name, country_code, latitude, longitude, distance_km)
                                        if len(r) == 6:
                                            _, pname, pcountry, plat, plon, _dist = r
                                        elif len(r) == 5:
                                            _, pname, pcountry, plat, plon = r
                                        else:
                                            # unexpected row shape
                                            try:
                                                print(f"geocode: unexpected row shape: {r}")
                                            except Exception:
                                                pass
                                            continue
                                        d = _haversine_km(lat_f, lon_f, float(plat), float(plon))
                                    except Exception:
                                        # continue to next candidate if conversion fails
                                        continue
                                    if best is None or d < best_d:
                                        best = (pname, pcountry)
                                        best_d = d
                                if best is not None and best_d is not None:
                                    city = best[0]
                                    country = best[1]
                                    try:
                                        print(f"geocode: local_geonames best match city={city!r} country={country!r} dist_km={best_d}")
                                    except Exception:
                                        pass
                                    success = True
                                    break
                                else:
                                    # no local candidates; try next provider
                                    continue

                            if prov == "geonames":
                                # Geonames reverse geocoding
                                gn_cfg = geocode_cfg.get("geonames", {})
                                username = gn_cfg.get("username")
                                if not username:
                                    continue
                                gn_endpoint = "http://api.geonames.org/findNearbyPlaceNameJSON"
                                params = {"lat": str(lat), "lng": str(lon), "username": username}
                                resp = requests.get(gn_endpoint, params=params, timeout=6)
                                if resp.status_code == 200:
                                    j = resp.json()
                                    geonames = j.get("geonames") or []
                                    if geonames:
                                        place = geonames[0]
                                        country = place.get("countryName")
                                        city = place.get("name")
                                        success = True
                                        break
                            elif prov == "nominatim":
                                endpoint = geocode_cfg.get("endpoint") or "https://nominatim.openstreetmap.org/reverse"
                                email = geocode_cfg.get("email") or ""
                                params = {"format": "jsonv2", "lat": str(lat), "lon": str(lon), "zoom": 10, "addressdetails": 1}
                                if email:
                                    params["email"] = email
                                headers = {"User-Agent": "DupDetector/1.0 (+https://example.invalid)"}
                                resp = requests.get(endpoint, params=params, headers=headers, timeout=10)
                                if resp.status_code == 200:
                                    j = resp.json()
                                    address = j.get("address") or {}
                                    country = address.get("country") or address.get("country_name")
                                    city = address.get("city") or address.get("town") or address.get("village") or address.get("municipality")
                                    success = True
                                    break
                                elif resp.status_code == 429:
                                    time.sleep(1)
                                    continue
                        except Exception:
                            # try next provider
                            continue

                        if success and (country or city):
                            # log what we are about to set/update for traceability
                            try:
                                print(f"geocode result for file id={f.id}: country={country!r}, city={city!r}")
                            except Exception:
                                pass
                            if country and getattr(f, "country", None) != country:
                                print(f"updating file id={f.id} country: {getattr(f, 'country', None)!r} -> {country!r}")
                                f.country = country
                                changed = True
                            if city and getattr(f, "city", None) != city:
                                print(f"updating file id={f.id} city: {getattr(f, 'city', None)!r} -> {city!r}")
                                f.city = city
                                changed = True
                            # Set geocode provenance flag according to where GPS came from
                            try:
                                # If GPS string matches the EXIF-derived gps variable above, treat as EXIF raw GPS
                                current_gps = getattr(f, 'gps', None)
                                if current_gps and current_gps == f"{lat},{lon}":
                                    # gps from EXIF + auto city/country
                                    f.geocode_provenance = 1
                                else:
                                    # gps present but not equal to EXIF-derived -> assume manual GPS
                                    f.geocode_provenance = 3
                                changed = True
                            except Exception:
                                pass
        except Exception:
            pass

        # media_type: prefer MIMEType then FileType
        mt = data.get("MIMEType") or data.get("FileType") or data.get("FileTypeExtension")
        if mt and getattr(f, "media_type", None) != mt:
            f.media_type = str(mt)
            changed = True

        # metadata_json: store the parsed exif object as a JSON string
        # NOTE: keep full exif JSON in the exif_data table (saved by save_exif).

        if changed:
            try:
                self.session.commit()
                self.session.refresh(f)
                # After commit, print final gps/country/city for traceability
                try:
                    final_gps = getattr(f, "gps", None)
                    final_country = getattr(f, "country", None)
                    final_city = getattr(f, "city", None)
                    print(f"final geocode for file id={f.id}: gps={final_gps!r}, country={final_country!r}, city={final_city!r}")
                except Exception:
                    pass
            except Exception:
                self.session.rollback()
                raise

        # After saving identifiers, attempt to link related files by identifier.
        # Prefer content_identifier grouping; fall back to photo_identifier.
        try:
            gid = None
            if f.content_identifier:
                gid = f.content_identifier
                # find all files with same content_identifier
                rows = self.session.query(File.id).filter(File.content_identifier == gid).all()
                ids = [r[0] for r in rows]
            elif f.photo_identifier:
                gid = f.photo_identifier
                rows = self.session.query(File.id).filter(File.photo_identifier == gid).all()
                ids = [r[0] for r in rows]
            else:
                ids = []

            if ids:
                canonical = min(ids)
                # update related_id for all files with this identifier that are not the canonical
                (self.session.query(File)
                    .filter(File.id.in_(ids))
                    .filter(File.id != canonical)
                    .update({"related_id": canonical, "updated_at": sa_func.current_timestamp()}, synchronize_session=False))
                # Ensure canonical row has related_id=None (or itself?) — keep as None to indicate canonical
                (self.session.query(File)
                    .filter_by(id=canonical)
                    .update({"related_id": None, "updated_at": sa_func.current_timestamp()}, synchronize_session=False))
                self.session.commit()
        except Exception:
            # On any failure during linking, rollback but do not raise — linking is best-effort
            try:
                self.session.rollback()
            except Exception:
                pass

        return f
