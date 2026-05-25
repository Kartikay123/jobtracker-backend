"""Pydantic schemas for User + auth."""

from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas._base import CamelModel


class UserBase(CamelModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr


class UserCreate(UserBase):
    """Body of POST /auth/signup."""

    password: str = Field(min_length=8, max_length=128)


class UserLogin(CamelModel):
    """Body of POST /auth/login."""

    email: EmailStr
    password: str


class UserOut(UserBase):
    """Anything the API ever returns as 'a user'. Never includes password_hash."""

    id: int
    created_at: datetime


class Token(CamelModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
