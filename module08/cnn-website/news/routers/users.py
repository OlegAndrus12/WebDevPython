"""Readers, and what each one has liked.

Nothing here authenticates. The reader is named in the path, so `user_id` is an
ordinary path parameter -- no session, no token, no `current_user`. That is why
the like routes live under `/api/users/{user_id}/` rather than `/api/me/`:
`me` only means something once a request can prove who it is.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, status

from ..dependencies import SessionDep
from ..models import User
from ..repository import Repository
from ..schemas import ArticleOut, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])

UserId = Path(..., ge=1, description="id of the reader")


async def _get_user_or_404(repo: Repository, user_id: int) -> User:
    user = await repo.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return user


@router.get("", response_model=list[UserOut], summary="List readers")
async def list_users(session: SessionDep) -> list[UserOut]:
    users = await Repository(session).list_users()
    return [UserOut.model_validate(user) for user in users]


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Username or email already taken"}},
    summary="Create a reader",
)
async def create_user(body: UserCreate, session: SessionDep) -> UserOut:
    repo = Repository(session)
    # Both columns are UNIQUE, so the database would refuse either way -- as an
    # IntegrityError, which surfaces as a 500. Checking first gives a 409 that
    # says which field clashed.
    if await repo.get_user_by_email(body.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if await repo.get_user_by_username(body.username) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")

    user = await repo.create_user(username=body.username, email=body.email)
    return UserOut.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserOut,
    responses={404: {"description": "No user with that id"}},
    summary="One reader",
)
async def get_user(session: SessionDep, user_id: int = UserId) -> UserOut:
    user = await _get_user_or_404(Repository(session), user_id)
    return UserOut.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    responses={404: {"description": "No user with that id"}},
    summary="Update a reader",
)
async def update_user(
    body: UserUpdate, session: SessionDep, user_id: int = UserId
) -> UserOut:
    repo = Repository(session)
    user = await _get_user_or_404(repo, user_id)

    # exclude_unset is what makes this a PATCH: a field the client left out is
    # absent here, so it keeps its current value.
    fields = body.model_dump(exclude_unset=True)

    # Only for a value that actually changed -- otherwise PATCHing a user with
    # its own email would 409 against itself.
    if "email" in fields and fields["email"] != user.email:
        if await repo.get_user_by_email(fields["email"]) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if "username" in fields and fields["username"] != user.username:
        if await repo.get_user_by_username(fields["username"]) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")

    user = await repo.update_user(user, **fields)
    return UserOut.model_validate(user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "No user with that id"}},
    summary="Delete a reader",
)
async def delete_user(session: SessionDep, user_id: int = UserId) -> None:
    repo = Repository(session)
    user = await _get_user_or_404(repo, user_id)
    await repo.delete_user(user)


@router.get(
    "/{user_id}/liked",
    response_model=list[ArticleOut],
    responses={404: {"description": "No user with that id"}},
    summary="Everything one reader has liked",
)
async def liked_articles(session: SessionDep, user_id: int = UserId) -> list[ArticleOut]:
    """Newest like first."""
    repo = Repository(session)
    await _get_user_or_404(repo, user_id)
    articles = await repo.list_liked_articles(user_id)
    return [ArticleOut.model_validate(article) for article in articles]


@router.post(
    "/{user_id}/articles/{article_id}/like",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "No such user, or no such article"}},
    summary="Like an article",
)
async def like_article(
    session: SessionDep, user_id: int = UserId, article_id: int = Path(..., ge=1)
) -> None:
    """Idempotent -- liking twice is a 204 both times, not a 409."""
    repo = Repository(session)
    await _get_user_or_404(repo, user_id)
    if await repo.get_article_by_id(article_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "article not found")
    await repo.like_article(user_id, article_id)


@router.delete(
    "/{user_id}/articles/{article_id}/like",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "No such user, or no such article"}},
    summary="Remove a like",
)
async def unlike_article(
    session: SessionDep, user_id: int = UserId, article_id: int = Path(..., ge=1)
) -> None:
    """Also idempotent: unliking something never liked is a 204."""
    repo = Repository(session)
    await _get_user_or_404(repo, user_id)
    if await repo.get_article_by_id(article_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "article not found")
    await repo.unlike_article(user_id, article_id)
