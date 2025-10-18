from sqlalchemy import Column, Integer, ForeignKey, Table
from dupdetector.models import Base


class FileTag(Base):
    __tablename__ = "file_tags"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
