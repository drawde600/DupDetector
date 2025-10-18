from sqlalchemy import Column, Integer, String
from dupdetector.models import Base


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
