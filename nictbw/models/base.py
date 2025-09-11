from sqlalchemy.orm import DeclarativeBase
from nictbw.db.metadata import metadata_obj


class Base(DeclarativeBase):
    metadata = metadata_obj
