"""SQLAlchemy declarative base. All ORM models inherit from `Base`."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Parent class for every ORM model.

    Alembic reads `Base.metadata` to autogenerate migrations, so make sure
    every model is imported (directly or transitively) by `app/models/__init__.py`.
    """

    pass
