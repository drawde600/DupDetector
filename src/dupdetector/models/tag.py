from sqlalchemy import Column, Integer, Text
from dupdetector.models import Base


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(Text, unique=True, nullable=False)
