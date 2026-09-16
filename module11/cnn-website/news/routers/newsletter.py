"""Turning the newsletter on and off, for a logged-in reader."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User
from ..repository import Repository
from ..schemas import SubscriptionIn
from ..security import auth_service

router = APIRouter(prefix="/api", tags=["newsletter"])


@router.put("/me/subscription", status_code=status.HTTP_204_NO_CONTENT)
async def set_subscription(
    body: SubscriptionIn,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
) -> None:
    await Repository(session).set_subscribed(current_user, body.subscribed)
