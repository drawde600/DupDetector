from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from dupdetector.models import Base


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    # Use length-limited String for indexed/unique columns to satisfy MySQL
    # requirements (MySQL doesn't allow indexing TEXT/BLOB without a key length).
    # Keep path <= 768 chars so the UNIQUE index fits InnoDB's default
    # max key length (3072 bytes) when using utf8mb4 (4 bytes/char).
    path = Column(String(768), unique=True, nullable=False)
    original_path = Column(String(1024), nullable=False)
    name = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    size = Column(Integer, nullable=False)
    media_type = Column(String(100), nullable=True)
    dimensions = Column(String(50), nullable=True)
    manufacturer = Column(String(255), nullable=True)
    # NOTE: detailed EXIF/metadata is stored in the separate exif_data table
    # to avoid slowing queries on the main files table.
    md5_hash = Column(String(64), nullable=False)
    photo_hash = Column(String(64), nullable=True)
    # Identifiers extracted from camera/vendor metadata useful for grouping
    content_identifier = Column(String(255), nullable=True, index=True)
    photo_identifier = Column(String(255), nullable=True, index=True)
    related_id = Column(Integer, nullable=True)
    is_duplicate = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)
    duplicate_of_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    # If a new file is created as a derivative (re-encode/rotate/resize) of an
    # existing DB row, set previous_id to the old row so manual metadata can be
    # inherited or audited. This is intentionally minimal and nullable.
    # If a new file is created as a derivative (re-encode/rotate/resize) of an
    # existing DB row, set previous_id to the old row so manual metadata can be
    # inherited or audited. This is intentionally minimal and nullable.
    previous_id = Column(Integer, ForeignKey("files.id"), nullable=True, index=True)

    # Photo taken timestamp (from EXIF) - different from DB created_at/updated_at
    taken_at = Column(DateTime, nullable=True, index=True)
    # taken_at provenance flag:
    # 1 = taken_at from EXIF (raw)
    # 2 = taken_at manually entered/overridden
    # 3 = taken_at inferred from filesystem timestamps (mtime)
    taken_at_provenance = Column(Integer, nullable=True, default=None)

    # GPS and human-readable location fields populated from GPS via optional reverse-geocoding
    gps = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True, index=True)
    city = Column(String(100), nullable=True, index=True)

    # Geocode provenance flag (do not deviate from current schema). Encoding:
    # 1 = (gps_raw from EXIF) + (auto_city + auto_country)
    # 2 = (gps_raw from EXIF) + (manual_city + manual_country)
    # 3 = (gps_manual provided) + (auto_city + auto_country)
    # 4 = (gps_manual provided) + (manual_city + manual_country)
    # Keep this as a small integer so it's easy to query and update.
    geocode_provenance = Column(Integer, nullable=True, default=None)
