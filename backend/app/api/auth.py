"""Authentication endpoints: register, login, refresh, me."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser, rate_limit_auth
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(rate_limit_auth)])


def _issue_tokens(user_id: int) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: DB) -> TokenPair:
    email = body.email.lower()
    existing = await db.execute(
        select(User).where(func.lower(User.email) == email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    user = User(
        email=email,
        username=body.username.strip(),
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _issue_tokens(user.id)


@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest, db: DB) -> TokenPair:
    result = await db.execute(
        select(User).where(func.lower(User.email) == body.email.lower())
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return _issue_tokens(user.id)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, db: DB) -> TokenPair:
    user_id = decode_token(body.refresh_token, expected_type="refresh")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return _issue_tokens(user.id)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
