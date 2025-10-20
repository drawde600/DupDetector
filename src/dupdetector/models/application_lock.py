"""Application lock model for database-level process coordination."""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from dupdetector.models import Base


class ApplicationLock(Base):
    """Table to track application locks for coordinating database access.

    Only one process should hold a lock for a given lock_name at a time.
    This prevents concurrent operations that could conflict.

    Example lock_names:
    - "scan": Running file scan operation
    - "deduplicate": Running deduplication operation
    - "purge": Running purge operation
    """
    __tablename__ = "application_locks"

    id = Column(Integer, primary_key=True)
    lock_name = Column(String(255), unique=True, nullable=False, index=True)
    process_id = Column(Integer, nullable=False)  # OS process ID
    hostname = Column(String(255), nullable=False)  # Machine hostname
    acquired_at = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration time
