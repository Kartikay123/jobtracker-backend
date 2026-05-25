"""Password hashing and JWT helpers.

Why these specific tools:
- passlib + bcrypt: industry default. passlib lets us migrate algorithms later
  (e.g. argon2) without changing call sites — old hashes keep working.
- python-jose: signs/verifies JWTs. We use HS256 (symmetric) because we're a
  single-service app; if you ever split into multiple services that need to
  verify tokens without sharing the secret, switch to RS256.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Passwords ---
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# --- JWT ---
def create_access_token(
    subject: str | int,
    expires_minutes: int | None = None,
) -> str:
    """Issue a signed JWT. `subject` (the user id) goes into the standard `sub` claim."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes if expires_minutes is not None else settings.JWT_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and verify a JWT. Returns None on any failure (expired, bad sig, malformed)."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
