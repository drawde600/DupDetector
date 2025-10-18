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
    gps = Column(String(100), nullable=True)
    # 'metadata' is a reserved attribute name on Declarative classes (Base.metadata),
    # so store file metadata in a column named 'metadata' but expose as 'metadata_json'
    metadata_json = Column('metadata', Text, nullable=True)
    md5_hash = Column(String(64), nullable=False)
    photo_hash = Column(String(64), nullable=True)
    related_id = Column(Integer, nullable=True)
    is_duplicate = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)
    duplicate_of_id = Column(Integer, ForeignKey("files.id"), nullable=True)
