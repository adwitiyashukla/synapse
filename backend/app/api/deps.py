from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.quota import DailyQuota
from app.core.ratelimit import SlidingWindowLimiter, client_key, enforce
from app.core.security import decode_token
from app.database import get_db
from app.models import ChatSession, User

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)

HOUR = 3600

auth_limiter = SlidingWindowLimiter(
    settings.rate_limit_auth, settings.rate_limit_window_seconds
)
chat_limiter = SlidingWindowLimiter(
    settings.rate_limit_chat, settings.rate_limit_window_seconds
)

demo_session_limiter = SlidingWindowLimiter(settings.demo_sessions_per_hour, HOUR)
demo_chat_limiter = SlidingWindowLimiter(settings.demo_messages_per_hour, HOUR)
demo_daily_quota = DailyQuota(settings.demo_daily_message_cap)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_token(credentials.credentials, expected_type="access")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]


async def get_owned_session(
    session_id: str, user: CurrentUser, db: DB
) -> ChatSession:
    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return session


def rate_limit_auth(request: Request) -> None:
    enforce(auth_limiter, request)


def rate_limit_chat(request: Request) -> None:
    enforce(chat_limiter, request)
    if not settings.demo_mode:
        return
    if not demo_chat_limiter.check(client_key(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Demo limit reached: {settings.demo_messages_per_hour} messages "
                "per hour. Run Synapse locally from the GitHub repo for unlimited use."
            ),
        )
    if not demo_daily_quota.try_consume():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "The shared demo has reached its daily message budget. "
                "Please try again tomorrow, or run Synapse locally with your own key."
            ),
        )


def rate_limit_demo_session(request: Request) -> None:
    if not demo_session_limiter.check(client_key(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many demo sessions from this address. Please try again later.",
        )
