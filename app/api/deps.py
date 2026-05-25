"""Reusable route dependencies.

The big one is `get_current_user` — extracts the JWT from the
`Authorization: Bearer <token>` header and resolves it to a User row.
Use it via the `CurrentUser` alias:

    @router.get("/me")
    async def me(current_user: CurrentUser): ...
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.deps import get_db
from app.models.user import User

# `tokenUrl` is what the /docs "Authorize" button calls; it doesn't need to
# accept the OAuth2 form format, just live at this path.
# auto_error=False so missing tokens give us our own 401 instead of FastAPI's.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_exc

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exc

    user_id = payload.get("sub")
    if not user_id:
        raise credentials_exc

    user = await db.get(User, int(user_id))
    if user is None:
        raise credentials_exc
    return user


# Shorthand annotation: `def route(current_user: CurrentUser): ...`
CurrentUser = Annotated[User, Depends(get_current_user)]
