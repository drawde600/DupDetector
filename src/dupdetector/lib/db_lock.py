"""Database-level locking for coordinating concurrent operations.

This module provides application-level locks stored in the database to prevent
conflicting operations from running simultaneously.
"""
from __future__ import annotations

import os
import socket
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, Generator

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from dupdetector.models.application_lock import ApplicationLock


class LockAcquisitionError(Exception):
    """Raised when a lock cannot be acquired."""
    pass


class DatabaseLock:
    """Context manager for acquiring and releasing database locks.

    Usage:
        with DatabaseLock(session, "scan") as lock:
            # Perform scan operation
            pass

    The lock is automatically released when exiting the context manager.
    """

    def __init__(
        self,
        session: Session,
        lock_name: str,
        timeout_seconds: int = 3600,
        wait_for_lock: bool = False,
        wait_timeout: int = 60
    ):
        """Initialize database lock.

        Args:
            session: SQLAlchemy session
            lock_name: Name of the lock (e.g., "scan", "deduplicate", "purge")
            timeout_seconds: Lock expiration timeout (default: 1 hour)
            wait_for_lock: If True, wait for lock to be released (default: False)
            wait_timeout: Max time to wait for lock in seconds (default: 60)
        """
        self.session = session
        self.lock_name = lock_name
        self.timeout_seconds = timeout_seconds
        self.wait_for_lock = wait_for_lock
        self.wait_timeout = wait_timeout
        self.lock_record: Optional[ApplicationLock] = None

    def acquire(self) -> None:
        """Acquire the lock.

        Raises:
            LockAcquisitionError: If lock cannot be acquired
        """
        process_id = os.getpid()
        hostname = socket.gethostname()
        expires_at = datetime.now() + timedelta(seconds=self.timeout_seconds)

        start_time = time.time()

        while True:
            # Check for existing lock
            existing_lock = self.session.query(ApplicationLock).filter_by(
                lock_name=self.lock_name
            ).first()

            if existing_lock:
                # Check if lock has expired
                if existing_lock.expires_at and existing_lock.expires_at < datetime.now():
                    # Lock expired, clean it up
                    self.session.delete(existing_lock)
                    try:
                        self.session.commit()
                    except Exception:
                        self.session.rollback()
                        # Another process may have deleted it, retry
                        continue
                else:
                    # Lock is held by another process
                    if not self.wait_for_lock:
                        raise LockAcquisitionError(
                            f"Lock '{self.lock_name}' is held by PID {existing_lock.process_id} "
                            f"on {existing_lock.hostname} (acquired at {existing_lock.acquired_at})"
                        )

                    # Wait for lock
                    elapsed = time.time() - start_time
                    if elapsed >= self.wait_timeout:
                        raise LockAcquisitionError(
                            f"Timeout waiting for lock '{self.lock_name}' "
                            f"(held by PID {existing_lock.process_id} on {existing_lock.hostname})"
                        )

                    print(f"Waiting for lock '{self.lock_name}' (held by PID {existing_lock.process_id})...")
                    time.sleep(2)
                    continue

            # Try to acquire lock
            lock_record = ApplicationLock(
                lock_name=self.lock_name,
                process_id=process_id,
                hostname=hostname,
                expires_at=expires_at
            )

            self.session.add(lock_record)

            try:
                self.session.commit()
                self.lock_record = lock_record
                return
            except IntegrityError:
                # Another process acquired the lock first
                self.session.rollback()
                if not self.wait_for_lock:
                    raise LockAcquisitionError(
                        f"Lock '{self.lock_name}' was acquired by another process"
                    )
                # Retry
                continue

    def release(self) -> None:
        """Release the lock."""
        if self.lock_record:
            try:
                self.session.delete(self.lock_record)
                self.session.commit()
                self.lock_record = None
            except Exception:
                self.session.rollback()
                raise

    def __enter__(self) -> DatabaseLock:
        """Context manager entry."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.release()


@contextmanager
def acquire_lock(
    session: Session,
    lock_name: str,
    timeout_seconds: int = 3600,
    wait_for_lock: bool = False,
    wait_timeout: int = 60
) -> Generator[None, None, None]:
    """Convenience context manager for acquiring a database lock.

    Args:
        session: SQLAlchemy session
        lock_name: Name of the lock
        timeout_seconds: Lock expiration timeout
        wait_for_lock: Whether to wait for lock to be released
        wait_timeout: Max time to wait for lock

    Yields:
        None

    Raises:
        LockAcquisitionError: If lock cannot be acquired

    Example:
        with acquire_lock(session, "scan"):
            # Perform scan operation
            pass
    """
    lock = DatabaseLock(
        session=session,
        lock_name=lock_name,
        timeout_seconds=timeout_seconds,
        wait_for_lock=wait_for_lock,
        wait_timeout=wait_timeout
    )

    with lock:
        yield


def cleanup_expired_locks(session: Session) -> int:
    """Clean up expired locks from the database.

    Args:
        session: SQLAlchemy session

    Returns:
        Number of locks cleaned up
    """
    now = datetime.now()

    expired_locks = session.query(ApplicationLock).filter(
        ApplicationLock.expires_at < now
    ).all()

    count = len(expired_locks)

    for lock in expired_locks:
        session.delete(lock)

    try:
        session.commit()
    except Exception:
        session.rollback()
        raise

    return count


def check_lock_exists(session: Session, lock_name: str) -> Optional[ApplicationLock]:
    """Check if a lock exists without acquiring it.

    Args:
        session: SQLAlchemy session
        lock_name: Name of the lock to check

    Returns:
        ApplicationLock if lock exists and is not expired, None otherwise
    """
    existing_lock = session.query(ApplicationLock).filter_by(
        lock_name=lock_name
    ).first()

    if existing_lock:
        # Check if lock has expired
        if existing_lock.expires_at and existing_lock.expires_at < datetime.now():
            # Lock expired, clean it up
            try:
                session.delete(existing_lock)
                session.commit()
            except Exception:
                session.rollback()
            return None

        return existing_lock

    return None


class DryRunLockChecker:
    """Helper for checking locks periodically during dry-run operations.

    This allows dry-run operations to:
    - Check for locks at startup (fail if locked)
    - Periodically check for new locks during execution (abort if locked)
    - Not acquire locks themselves (read-only)
    """

    def __init__(
        self,
        session: Session,
        lock_name: str,
        check_interval: int = 60
    ):
        """Initialize dry-run lock checker.

        Args:
            session: SQLAlchemy session
            lock_name: Name of the lock to check
            check_interval: How often to check for locks (seconds)
        """
        self.session = session
        self.lock_name = lock_name
        self.check_interval = check_interval
        self.last_check_time = 0.0

    def check_at_start(self) -> None:
        """Check if lock exists at startup.

        Raises:
            LockAcquisitionError: If lock is currently held
        """
        existing_lock = check_lock_exists(self.session, self.lock_name)

        if existing_lock:
            raise LockAcquisitionError(
                f"Lock '{self.lock_name}' is currently held by PID {existing_lock.process_id} "
                f"on {existing_lock.hostname} (acquired at {existing_lock.acquired_at}). "
                f"Cannot run dry-run while operation is active."
            )

        self.last_check_time = time.time()

    def periodic_check(self) -> None:
        """Periodically check if a lock has been acquired.

        Should be called regularly during dry-run operation.
        Only checks if check_interval has elapsed.

        Raises:
            LockAcquisitionError: If lock has been acquired since last check
        """
        current_time = time.time()
        elapsed = current_time - self.last_check_time

        if elapsed >= self.check_interval:
            existing_lock = check_lock_exists(self.session, self.lock_name)

            if existing_lock:
                raise LockAcquisitionError(
                    f"Lock '{self.lock_name}' was acquired by PID {existing_lock.process_id} "
                    f"on {existing_lock.hostname} during dry-run. Aborting dry-run operation."
                )

            self.last_check_time = current_time
