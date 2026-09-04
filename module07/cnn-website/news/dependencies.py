"""Shared dependency aliases, so routes read as one line of signature."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db

SessionDep = Annotated[AsyncSession, Depends(get_db)]
