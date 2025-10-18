from sqlalchemy.orm import declarative_base

Base = declarative_base()

from .file import File  # noqa: F401
from .tag import Tag  # noqa: F401
from .filetag import FileTag  # noqa: F401
