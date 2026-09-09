"""Registration and login. JSON in, a bearer token out."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ..dependencies import SessionDep
from ..models import User
from ..repository import Repository
from ..schemas import Token, UserCreate, UserOut
from ..security import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, session: SessionDep) -> UserOut:
    repo = Repository(session)
    # Both columns are UNIQUE, so the database would refuse either way -- as an
    # IntegrityError, which surfaces as a 500. Checking first gives a 409.
    if await repo.get_user_by_email(body.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if await repo.get_user_by_username(body.username) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")

    return await repo.create_user(
        username=body.username,
        email=body.email,
        hashed_password=await auth_service.hash_password(body.password),
    )


@router.post("/login", response_model=Token)
async def login(
    session: SessionDep, form: OAuth2PasswordRequestForm = Depends()
) -> Token:
    """OAuth2 password flow, so the body is form-urlencoded and the email
    arrives in a field named `username`. That is the spec's name, not a bug.
    """
    user = await Repository(session).get_user_by_email(form.username)
    # One message for both cases: saying which half was wrong tells an attacker
    # whether the address is registered.
    if user is None or not await auth_service.verify_password(
        form.password, user.hashed_password
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid email or password"
        )

    return Token(access_token=await auth_service.create_access_token(user.email))


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(auth_service.get_current_user)) -> UserOut:
    """Whoever the bearer token belongs to. Used by the navbar to show a name."""
    return current_user
