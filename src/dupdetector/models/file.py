from sqlalchemy import Column, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from dupdetector.models import Base


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    path = Column(Text, unique=True, nullable=False)
    original_path = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    original_name = Column(Text, nullable=False)
    size = Column(Integer, nullable=False)
    media_type = Column(Text, nullable=True)
    dimensions = Column(Text, nullable=True)
    manufacturer = Column(Text, nullable=True)
    gps = Column(Text, nullable=True)
    # 'metadata' is a reserved attribute name on Declarative classes (Base.metadata),
    # so store file metadata in a column named 'metadata' but expose as 'metadata_json'
    metadata_json = Column('metadata', Text, nullable=True)
    md5_hash = Column(Text, nullable=False)
    photo_hash = Column(Text, nullable=True)
    related_id = Column(Integer, nullable=True)
    is_duplicate = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)
    duplicate_of_id = Column(Integer, ForeignKey("files.id"), nullable=True)
