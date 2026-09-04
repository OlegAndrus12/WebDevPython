
from fastapi import APIRouter, HTTPException, status
from ..dependencies import SessionDep
from ..schemas import UserCreate, UserOut
from ..repository import Repository
from ..security import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])



@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, session: SessionDep):
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

    return user