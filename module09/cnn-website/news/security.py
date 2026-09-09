"""Password hashing and JWT issue/verify, behind one service object."""

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from .dependencies import SessionDep
from .repository import Repository
from .settings import settings


class AuthService:
    ALGORITHM = "HS256"
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    # tokenUrl is what /docs uses to drive its Authorize button; it does not
    # route anything itself.
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

    # WWW-Authenticate is required by RFC 6750 on a 401 from a bearer scheme.
    CREDENTIALS_EXCEPTION = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    async def hash_password(self, password: str) -> str:
        return self.pwd_context.hash(password)

    async def verify_password(self, plain_password, hashed_password):
        return self.pwd_context.verify(plain_password, hashed_password)

    async def create_access_token(self, email):
        payload = {
            "scope": "access_token",
            "sub": email,
            "exp": datetime.now(timezone.utc) + timedelta(
                minutes=settings.access_token_expire_minutes
            ),
        }
        return jwt.encode(
            payload, settings.secret_key.get_secret_value(), algorithm=self.ALGORITHM
        )

    async def get_current_user(self, session: SessionDep, token: str = Depends(oauth2_scheme)):
        """The dependency every protected route depends on.

        A JWT is signed, not encrypted: anyone holding one can read its claims.
        What the signature buys is that nobody can forge or alter one.
        """
        try:
            payload = jwt.decode(
                token, settings.secret_key.get_secret_value(), algorithms=[self.ALGORITHM]
            )
            email = payload.get("sub")
            if email is None:
                raise self.CREDENTIALS_EXCEPTION
        except JWTError as e:
            raise self.CREDENTIALS_EXCEPTION from e

        # The token proves the claim was signed; it does not prove the row is
        # still there, so the user is looked up on every request.
        user = await Repository(session).get_user_by_email(email)
        if user is None:
            raise self.CREDENTIALS_EXCEPTION

        return user


auth_service = AuthService()
