from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from urllib.parse import quote_plus, unquote_plus
import os
from urllib.parse import urlparse, urlunparse


def get_engine(url: str | None = None):
    """Create a SQLAlchemy engine. Defaults to in-memory SQLite when url is None."""
    url = url or "sqlite:///:memory:"
    # Normalize semicolon-style MySQL connection strings or plain paths
    url = normalize_db_url(url)
    # Enable pool_pre_ping to reduce spurious auth/connection issues on some servers
    engine = create_engine(url, echo=False, future=True, pool_pre_ping=True)
    return engine


def normalize_db_url(value: str) -> str:
    """Normalize different DB connection representations into a SQLAlchemy URL.

    - If value already looks like a URL (contains '://'), return as-is.
    - If value is a semicolon-separated MySQL-style string (key=val;...), convert
      to a mysql+pymysql SQLAlchemy URL.
    - If value looks like a filesystem path, convert to sqlite URL.
    """
    if not value:
        return value

    # already a URL (e.g. sqlite, mysql+pymysql, etc.).
    # Only mutate it when username/password need percent-encoding; otherwise
    # return the original value unchanged.
    if "://" in value:
        try:
            parsed = urlparse(value)
        except Exception:
            return value

        # if credentials present, percent-encode and rebuild the netloc
        # Unquote first to avoid double-encoding when callers already pass
        # percent-encoded credentials (e.g., SqlP%40ss8).
        if parsed.username or parsed.password:
            username_raw = unquote_plus(parsed.username) if parsed.username else None
            password_raw = unquote_plus(parsed.password) if parsed.password else None
            username = quote_plus(username_raw) if username_raw is not None else None
            password = quote_plus(password_raw) if password_raw is not None else None
            # rebuild netloc
            hostport = parsed.hostname or ""
            if parsed.port:
                hostport = f"{hostport}:{parsed.port}"
            userinfo = ""
            if username is not None:
                userinfo = username
                if password is not None:
                    userinfo = f"{userinfo}:{password}"
                userinfo = f"{userinfo}@"
            new_netloc = f"{userinfo}{hostport}"
            rebuilt = parsed._replace(netloc=new_netloc)
            return urlunparse(rebuilt)

        # no credentials to encode -> return original URL
        return value

    # semicolon-delimited key=value pairs (common Windows MySQL-style DSN)
    if "=" in value and ";" in value:
        # parse into dict
        parts = [p.strip() for p in value.split(";") if p.strip()]
        kv = {}
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                kv[k.strip().lower()] = v.strip()

        host = kv.get("server") or kv.get("host")
        user = kv.get("user") or kv.get("uid") or kv.get("username")
        password = kv.get("password") or kv.get("pwd")
        port = kv.get("port")
        database = kv.get("database") or kv.get("initial catalog") or kv.get("dbname")
        sslmode = kv.get("sslmode") or kv.get("ssl")

        if host and user and database:
            # quote credentials
            user_q = quote_plus(user)
            pwd_q = quote_plus(password) if password is not None else ""
            port_part = f":{port}" if port else ""
            url = f"mysql+pymysql://{user_q}:{pwd_q}@{host}{port_part}/{database}"
            if sslmode:
                # If sslmode indicates disabled/none, don't add. Otherwise pass through.
                if sslmode.lower() not in ("none", "disable", "disabled", "false"):
                    # append as query param
                    url = url + f"?ssl_mode={quote_plus(sslmode)}"
            return url

    # treat as a filesystem path -> sqlite
    # normalize backslashes for sqlite URL
    v = value.replace("\\", "/")
    if os.path.exists(v) or "/" in v or "\\" in value:
        return f"sqlite:///{v}"

    # fallback: return original value
    return value


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
