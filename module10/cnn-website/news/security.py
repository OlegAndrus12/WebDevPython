"""Password hashing and JWT issuing/verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .models import Role, User
from .repository import Repository
from .settings import settings


class AuthService:
    ALGORITHM = "HS256"
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

    CREDENTIALS_EXCEPTION = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    async def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    async def _create_token(self, email: str, scope: str, expires_minutes: int) -> str:
        """The one place a token is signed. Every kind carries the same three"""
        payload = {
            "sub": email,
            "scope": scope,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
        }
        return jwt.encode(
            payload, settings.secret_key.get_secret_value(), algorithm=self.ALGORITHM
        )

    async def create_access_token(self, email: str, expires_minutes: int | None = None) -> str:
        return await self._create_token(
            email,
            "access_token",
            expires_minutes or settings.access_token_expire_minutes,
        )

    async def create_verification_token(self, email: str) -> str:
        return await self._create_token(
            email, "verification_token", settings.verification_token_expire_minutes
        )

    async def decode_verification_token(self, token: str) -> str:
        """The address a verification link is good for, or an HTTP error."""
        try:
            payload = jwt.decode(
                token, settings.secret_key.get_secret_value(), algorithms=[self.ALGORITHM]
            )
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid token for email verification",
            ) from exc

        if payload.get("scope") != "verification_token":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid scope for token"
            )
        email = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid scope for token"
            )
        return email

    async def get_current_user(
        self,
        token: str = Depends(oauth2_scheme),
        session: AsyncSession = Depends(get_db),
    ) -> User:
        """`Depends(oauth2_scheme)` above is what makes a route 401 with no"""
        try:
            payload = jwt.decode(
                token, settings.secret_key.get_secret_value(), algorithms=[self.ALGORITHM]
            )
            if payload.get("scope") != "access_token":
                raise self.CREDENTIALS_EXCEPTION
            email = payload.get("sub")
            if email is None:
                raise self.CREDENTIALS_EXCEPTION
        except JWTError as exc:
            raise self.CREDENTIALS_EXCEPTION from exc

        user = await Repository(session).get_user_by_email(email)
        if user is None:
            raise self.CREDENTIALS_EXCEPTION
        return user

    async def get_current_admin(
        self,
        token: str = Depends(oauth2_scheme),
        session: AsyncSession = Depends(get_db),
    ) -> User:
        current_user = await self.get_current_user(token, session)
        if current_user.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins only",
            )
        return current_user


auth_service = AuthService()
