"""Registration, login, and email verification. JSON in, a bearer token out."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..mail import send_verification_email
from ..models import User
from ..repository import Repository
from ..schemas import Message, RequestEmail, Token, UserCreate, UserOut
from ..security import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

NOT_VERIFIED_DETAIL = "Email is not verified"


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    repo = Repository(session)
    if await repo.get_user_by_email(body.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if await repo.get_user_by_username(body.username) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")

    user = await repo.create_user(
        username=body.username,
        email=body.email,
        hashed_password=await auth_service.hash_password(body.password),
    )

    background_tasks.add_task(
        send_verification_email, user.email, user.username, str(request.base_url)
    )
    return user


@router.post("/login", response_model=Token)
async def login(
    form: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(get_db)
) -> Token:
    user = await Repository(session).get_user_by_email(form.username)
    if user is None or not await auth_service.verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.confirmed:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, NOT_VERIFIED_DETAIL)
    return Token(access_token=await auth_service.create_access_token(user.email))


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(auth_service.get_current_user)) -> UserOut:
    return current_user


@router.get("/confirmed_email/{token}", response_model=Message)
async def confirmed_email(token: str, session: AsyncSession = Depends(get_db)) -> Message:
    """The target of the link in the email. Idempotent -- a link clicked twice,"""
    email = await auth_service.decode_verification_token(token)
    repo = Repository(session)

    user = await repo.get_user_by_email(email)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Verification error")
    if user.confirmed:
        return Message(message="Your email is already confirmed")

    await repo.confirm_email(email)
    return Message(message="Email confirmed")


@router.post("/request_email", response_model=Message)
async def request_email(
    body: RequestEmail,
    background_tasks: BackgroundTasks,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> Message:
    """Send another link, for when the first one expired or never arrived."""
    user = await Repository(session).get_user_by_email(body.email)
    if user is not None and not user.confirmed:
        background_tasks.add_task(
            send_verification_email, user.email, user.username, str(request.base_url)
        )
    return Message(message="Check your email for a confirmation link.")
