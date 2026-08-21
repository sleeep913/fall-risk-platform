from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_token,
    decode_token,
    token_fingerprint,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User


class AuthenticationError(Exception):
    pass


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    user: User


async def authenticate_user(
    *, username: str, password: str, session: AsyncSession
) -> User:
    normalized_username = username.strip().lower()
    user = await session.scalar(select(User).where(User.username == normalized_username))
    encoded_password = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_valid = verify_password(password, encoded_password)
    if user is None or not password_valid or not user.is_active:
        raise AuthenticationError("Invalid credentials")
    return user


async def issue_token_pair(
    *, user: User, session: AsyncSession, settings: Settings
) -> IssuedTokens:
    access_delta = timedelta(minutes=settings.access_token_expire_minutes)
    refresh_delta = timedelta(days=settings.refresh_token_expire_days)
    access_token, _ = create_token(
        subject=user.id,
        token_type="access",
        expires_delta=access_delta,
        settings=settings,
    )
    refresh_token, refresh_claims = create_token(
        subject=user.id,
        token_type="refresh",
        expires_delta=refresh_delta,
        settings=settings,
    )
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_fingerprint(refresh_claims.jti),
            expires_at=refresh_claims.expires_at,
        )
    )
    await session.commit()
    return IssuedTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=int(access_delta.total_seconds()),
        user=user,
    )


async def rotate_refresh_token(
    *, refresh_token: str, session: AsyncSession, settings: Settings
) -> IssuedTokens:
    try:
        claims = decode_token(refresh_token, expected_type="refresh", settings=settings)
    except InvalidTokenError as exc:
        raise AuthenticationError("Invalid refresh token") from exc

    stored_token = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_fingerprint(claims.jti),
            RefreshToken.user_id == claims.subject,
        )
    )
    now = datetime.now(UTC)
    if (
        stored_token is None
        or stored_token.revoked_at is not None
        or _as_utc(stored_token.expires_at) <= now
    ):
        raise AuthenticationError("Invalid refresh token")

    user = await session.scalar(select(User).where(User.id == claims.subject))
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid refresh token")

    stored_token.revoked_at = now
    issued = await issue_token_pair(user=user, session=session, settings=settings)
    new_claims = decode_token(
        issued.refresh_token, expected_type="refresh", settings=settings
    )
    stored_token.replaced_by_hash = token_fingerprint(new_claims.jti)
    await session.commit()
    return issued


async def revoke_refresh_token(
    *, refresh_token: str, user: User, session: AsyncSession, settings: Settings
) -> None:
    try:
        claims = decode_token(refresh_token, expected_type="refresh", settings=settings)
    except InvalidTokenError as exc:
        raise AuthenticationError("Invalid refresh token") from exc
    if claims.subject != user.id:
        raise AuthenticationError("Invalid refresh token")

    stored_token = await session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_fingerprint(claims.jti),
            RefreshToken.user_id == user.id,
        )
    )
    if stored_token is None or stored_token.revoked_at is not None:
        raise AuthenticationError("Invalid refresh token")
    stored_token.revoked_at = datetime.now(UTC)
    await session.commit()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

