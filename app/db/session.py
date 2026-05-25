"""Async SQLAlchemy engine and session factory.

Why these settings:
- echo=settings.is_dev: logs every SQL statement to stdout in development.
- pool_pre_ping=True: cheaply pings the connection before checkout, avoiding
  stale-connection errors after the DB restarts or a network blip.
- expire_on_commit=False: with async, expiring objects on commit triggers
  implicit lazy loads that fail because there's no sync IO. Standard pattern.
- autoflush=False: gives you explicit control of when SQL gets emitted.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.is_dev,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)
