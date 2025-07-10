import datetime
from typing import Any, Dict

from sqlalchemy import Column, DateTime, Integer, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, relationship

from db_domains.db import Base


def to_dict(obj: DeclarativeBase) -> Dict[str, Any]:
    """
    Convert an SQLAlchemy model instance into a dictionary.
    """
    data = {}  # Initialize an empty dictionary

    # Iterate over all columns of the model
    for column in obj.__table__.columns.keys():
        column_name = column
        column_value = getattr(obj, column_name)
        data[column_name] = column_value

    return data


def utc_now():
    return datetime.datetime.now(datetime.UTC)


class CreateUpdateTime(Base):
    __abstract__ = True

    created_at = Column(DateTime, default=utc_now)
    modified_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)


class CreateByUpdateBy(Base):
    __abstract__ = True

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    modified_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    @declared_attr
    def creator(cls):
        return relationship("User", foreign_keys=[cls.created_by])

    @declared_attr
    def modifier(cls):
        return relationship("User", foreign_keys=[cls.modified_by])
