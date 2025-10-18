from typing import Iterable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func as sa_func
from sqlalchemy.orm import Session

from dupdetector.models.file import File
from dupdetector.models.tag import Tag


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

        f = File(**kwargs)
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
