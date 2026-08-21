from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from jwt import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import FileResponse

from app.core.config import Settings
from app.core.database import get_app_settings, get_db_session
from app.models.offline_video import OfflineVideo
from app.models.user import User
from app.modules.auth.dependencies import require_admin
from app.modules.offline_videos.service import (
    MEDIA_TYPES,
    OfflineVideoService,
    OfflineVideoTranscodeError,
    OfflineVideoUnavailableError,
)
from app.schemas.offline_video import (
    OfflineVideoLibraryStatus,
    OfflineVideoPlaybackTicket,
    OfflineVideoRead,
    OfflineVideoScanResponse,
    OfflineVideoUpdate,
)

router = APIRouter(prefix="/offline-videos", tags=["offline-videos"])


def get_offline_video_service(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> OfflineVideoService:
    return OfflineVideoService(settings)


@router.get("/library", response_model=OfflineVideoLibraryStatus)
async def library_status(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[OfflineVideoService, Depends(get_offline_video_service)],
    _: Annotated[User, Depends(require_admin)],
) -> OfflineVideoLibraryStatus:
    return await service.library_status(session)


@router.post("/scan", response_model=OfflineVideoScanResponse)
async def scan_library(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[OfflineVideoService, Depends(get_offline_video_service)],
    _: Annotated[User, Depends(require_admin)],
) -> OfflineVideoScanResponse:
    return await service.scan(session)


@router.get("", response_model=list[OfflineVideoRead])
async def list_videos(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[OfflineVideoService, Depends(get_offline_video_service)],
    _: Annotated[User, Depends(require_admin)],
) -> list[OfflineVideoRead]:
    return await service.list_videos(session)


@router.patch("/{video_id}", response_model=OfflineVideoRead)
async def update_video(
    video_id: int,
    update: OfflineVideoUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[OfflineVideoService, Depends(get_offline_video_service)],
    _: Annotated[User, Depends(require_admin)],
) -> OfflineVideoRead:
    video = await service.update_video(session, video_id, update)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return video


@router.post("/{video_id}/playback-ticket", response_model=OfflineVideoPlaybackTicket)
async def create_playback_ticket(
    video_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[OfflineVideoService, Depends(get_offline_video_service)],
    _: Annotated[User, Depends(require_admin)],
) -> OfflineVideoPlaybackTicket:
    try:
        ticket = await service.create_playback_ticket(session, video_id)
    except OfflineVideoUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "video_unavailable", "message": str(exc)},
        ) from exc
    except OfflineVideoTranscodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "video_transcode_failed", "message": str(exc)},
        ) from exc
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return ticket


@router.get("/{video_id}/stream", response_class=FileResponse)
async def stream_video(
    video_id: int,
    ticket: Annotated[str, Query(min_length=1)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[OfflineVideoService, Depends(get_offline_video_service)],
) -> FileResponse:
    try:
        service.validate_playback_ticket(ticket, video_id)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired playback ticket",
        ) from exc
    video = await session.get(OfflineVideo, video_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    try:
        path = service.resolve_browser_playback_path(video)
    except OfflineVideoUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video file is not available",
        ) from exc
    return FileResponse(
        path,
        media_type=MEDIA_TYPES.get(path.suffix.lower(), video.media_type),
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
