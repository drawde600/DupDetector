from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_engine(url: str | None = None):
    """Create a SQLAlchemy engine. Defaults to in-memory SQLite when url is None."""
    url = url or "sqlite:///:memory:"
    engine = create_engine(url, echo=False, future=True)
    return engine


def get_sessionmaker(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine):
    """Create all tables using metadata from the models package."""
    # Import models lazily to avoid circular imports at package import time
    from dupdetector.models import Base

    Base.metadata.create_all(engine)


class InMemoryAdapter:
    """Lightweight in-memory DB adapter for tests.

    Usage:
        adapter = InMemoryAdapter()
        session = adapter.session()
    """

    def __init__(self):
        self.engine = get_engine("sqlite:///:memory:")
        self.Session = get_sessionmaker(self.engine)
        init_db(self.engine)

    def session(self):
        return self.Session()
