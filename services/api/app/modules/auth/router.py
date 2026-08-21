from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.database import get_app_settings, get_db_session
from app.models.user import User
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.service import (
    AuthenticationError,
    authenticate_user,
    issue_token_pair,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> TokenResponse:
    try:
        user = await authenticate_user(
            username=payload.username,
            password=payload.password,
            session=session,
        )
        issued = await issue_token_pair(user=user, session=session, settings=settings)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        ) from exc
    _set_refresh_cookie(response, issued.refresh_token, settings)
    return TokenResponse(**issued.__dict__)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> TokenResponse:
    refresh_cookie = request.cookies.get(settings.refresh_cookie_name)
    try:
        if not refresh_cookie:
            raise AuthenticationError("Missing refresh token")
        issued = await rotate_refresh_token(
            refresh_token=refresh_cookie,
            session=session,
            settings=settings,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc
    _set_refresh_cookie(response, issued.refresh_token, settings)
    return TokenResponse(**issued.__dict__)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> Response:
    refresh_cookie = request.cookies.get(settings.refresh_cookie_name)
    try:
        if not refresh_cookie:
            raise AuthenticationError("Missing refresh token")
        await revoke_refresh_token(
            refresh_token=refresh_cookie,
            user=user,
            session=session,
            settings=settings,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=f"{settings.api_v1_prefix}/auth",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserRead)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=f"{settings.api_v1_prefix}/auth",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
