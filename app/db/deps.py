"""FastAPI dependency that yields a database session per request.

Usage in a route:

    from fastapi import Depends
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.deps import get_db

    @router.get("/items")
    async def list_items(db: AsyncSession = Depends(get_db)):
        ...
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    # `async with` handles commit/rollback/close on exit; if the route raises,
    # the session is rolled back automatically.
    async with AsyncSessionLocal() as session:
        yield session
