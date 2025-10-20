from sqlalchemy import Column, Integer, ForeignKey, Table, DateTime
from sqlalchemy.sql import func
from dupdetector.models import Base


class FileTag(Base):
    __tablename__ = "file_tags"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    priority = Column(Integer, nullable=False, default=0)  # For tag ordering in rename format
    created_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)
