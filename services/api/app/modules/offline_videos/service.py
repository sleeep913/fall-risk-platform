import asyncio
import hashlib
import re
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from imageio_ffmpeg import get_ffmpeg_exe
from jwt import InvalidTokenError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.offline_video import OfflineVideo, OfflineVideoLabel, OfflineVideoOrigin
from app.schemas.offline_video import (
    OfflineVideoLibraryStatus,
    OfflineVideoPlaybackTicket,
    OfflineVideoRead,
    OfflineVideoScanResponse,
    OfflineVideoUpdate,
)

MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
}
BROWSER_NATIVE_EXTENSIONS = {".mp4", ".webm"}
_TRANSCODE_LOCKS: dict[str, asyncio.Lock] = {}


class OfflineVideoUnavailableError(Exception):
    pass


class OfflineVideoTranscodeError(Exception):
    pass


@dataclass(frozen=True)
class DiscoveredVideo:
    relative_path: str
    file_name: str
    display_name: str
    dataset_name: str | None
    label: OfflineVideoLabel
    media_type: str
    size_bytes: int
    file_modified_at: datetime


class OfflineVideoService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def list_videos(self, session: AsyncSession) -> list[OfflineVideoRead]:
        videos = (
            await session.scalars(
                select(OfflineVideo).order_by(
                    OfflineVideo.is_available.desc(),
                    OfflineVideo.dataset_name,
                    OfflineVideo.display_name,
                    OfflineVideo.id,
                )
            )
        ).all()
        return [to_offline_video_read(video) for video in videos]

    async def library_status(self, session: AsyncSession) -> OfflineVideoLibraryStatus:
        total_count = await session.scalar(select(func.count()).select_from(OfflineVideo))
        available_count = await session.scalar(
            select(func.count())
            .select_from(OfflineVideo)
            .where(OfflineVideo.is_available.is_(True))
        )
        labeled_count = await session.scalar(
            select(func.count())
            .select_from(OfflineVideo)
            .where(
                OfflineVideo.is_available.is_(True),
                OfflineVideo.label != OfflineVideoLabel.UNKNOWN,
            )
        )
        dataset_count = await session.scalar(
            select(func.count(func.distinct(OfflineVideo.dataset_name))).where(
                OfflineVideo.is_available.is_(True),
                OfflineVideo.dataset_name.is_not(None),
            )
        )
        last_scanned_at = await session.scalar(
            select(func.max(OfflineVideo.last_scanned_at))
        )
        return OfflineVideoLibraryStatus(
            root_hint="data/offline-videos",
            supported_extensions=sorted(MEDIA_TYPES),
            total_count=total_count or 0,
            available_count=available_count or 0,
            labeled_count=labeled_count or 0,
            dataset_count=dataset_count or 0,
            last_scanned_at=last_scanned_at,
        )

    async def scan(self, session: AsyncSession) -> OfflineVideoScanResponse:
        root = self.root
        root.mkdir(parents=True, exist_ok=True)
        discovered = await asyncio.to_thread(discover_videos, root)
        now = datetime.now(UTC)
        existing = {
            video.relative_path: video
            for video in (await session.scalars(select(OfflineVideo))).all()
        }
        for video in existing.values():
            video.is_available = False

        created = 0
        updated = 0
        for item in discovered:
            video = existing.get(item.relative_path)
            if video is None:
                video = OfflineVideo(
                    relative_path=item.relative_path,
                    file_name=item.file_name,
                    display_name=item.display_name,
                    dataset_name=item.dataset_name,
                    origin=OfflineVideoOrigin.OTHER,
                    label=item.label,
                    media_type=item.media_type,
                    size_bytes=item.size_bytes,
                    is_available=True,
                    file_modified_at=item.file_modified_at,
                    last_scanned_at=now,
                )
                session.add(video)
                existing[item.relative_path] = video
                created += 1
            else:
                video.file_name = item.file_name
                video.media_type = item.media_type
                video.size_bytes = item.size_bytes
                video.is_available = True
                video.file_modified_at = item.file_modified_at
                video.last_scanned_at = now
                updated += 1

        await session.commit()
        return OfflineVideoScanResponse(
            created=created,
            updated=updated,
            missing=sum(not video.is_available for video in existing.values()),
            total=len(discovered),
            scanned_at=now,
        )

    async def update_video(
        self, session: AsyncSession, video_id: int, update: OfflineVideoUpdate
    ) -> OfflineVideoRead | None:
        video = await session.get(OfflineVideo, video_id)
        if video is None:
            return None
        for field, value in update.model_dump(exclude_unset=True).items():
            setattr(video, field, value)
        await session.commit()
        await session.refresh(video)
        return to_offline_video_read(video)

    async def create_playback_ticket(
        self, session: AsyncSession, video_id: int
    ) -> OfflineVideoPlaybackTicket | None:
        video = await session.get(OfflineVideo, video_id)
        if video is None:
            return None
        _, transcoded = await self.prepare_browser_playback(video)
        now = datetime.now(UTC)
        expires_at = now + timedelta(
            seconds=self._settings.offline_playback_ticket_expire_seconds
        )
        ticket = jwt.encode(
            {
                "sub": str(video.id),
                "type": "offline_video_playback",
                "jti": str(uuid.uuid4()),
                "iat": now,
                "exp": expires_at,
            },
            self._settings.jwt_secret,
            algorithm=self._settings.jwt_algorithm,
        )
        return OfflineVideoPlaybackTicket(
            url=f"/api/v1/offline-videos/{video.id}/stream?ticket={ticket}",
            expires_at=expires_at,
            transcoded=transcoded,
        )

    def validate_playback_ticket(self, ticket: str, video_id: int) -> None:
        try:
            payload = jwt.decode(
                ticket,
                self._settings.jwt_secret,
                algorithms=[self._settings.jwt_algorithm],
                options={"require": ["sub", "type", "jti", "iat", "exp"]},
            )
            if (
                payload["type"] != "offline_video_playback"
                or int(payload["sub"]) != video_id
            ):
                raise InvalidTokenError("Playback ticket does not match the video")
        except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise InvalidTokenError("Invalid or expired playback ticket") from exc

    @property
    def root(self) -> Path:
        return self._settings.offline_video_root.expanduser().resolve()

    def resolve_available_path(self, video: OfflineVideo) -> Path:
        root = self.root
        candidate = (root / Path(video.relative_path)).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise OfflineVideoUnavailableError("Offline video file is not available")
        if candidate.suffix.lower() not in MEDIA_TYPES:
            raise OfflineVideoUnavailableError("Offline video type is not supported")
        return candidate

    async def prepare_browser_playback(self, video: OfflineVideo) -> tuple[Path, bool]:
        source = self.resolve_available_path(video)
        if source.suffix.lower() in BROWSER_NATIVE_EXTENSIONS:
            return source, False

        target = self._transcode_target(video)
        if target.is_file() and target.stat().st_size > 0:
            return target, True

        lock = _TRANSCODE_LOCKS.setdefault(str(target), asyncio.Lock())
        async with lock:
            if not target.is_file() or target.stat().st_size == 0:
                await asyncio.to_thread(
                    transcode_video,
                    source,
                    target,
                    self._settings.offline_video_transcode_timeout_seconds,
                )
        return target, True

    def resolve_browser_playback_path(self, video: OfflineVideo) -> Path:
        source = self.resolve_available_path(video)
        if source.suffix.lower() in BROWSER_NATIVE_EXTENSIONS:
            return source
        target = self._transcode_target(video)
        if not target.is_file() or target.stat().st_size == 0:
            raise OfflineVideoUnavailableError(
                "Browser-compatible playback file has not been prepared"
            )
        return target

    def _transcode_target(self, video: OfflineVideo) -> Path:
        fingerprint = hashlib.sha256(
            (
                f"{video.relative_path}\0{video.size_bytes}\0"
                f"{video.file_modified_at.isoformat()}"
            ).encode()
        ).hexdigest()[:24]
        return self._settings.offline_video_cache_root.expanduser().resolve() / (
            f"{fingerprint}.mp4"
        )


def discover_videos(root: Path) -> list[DiscoveredVideo]:
    root = root.resolve()
    videos: list[DiscoveredVideo] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in MEDIA_TYPES:
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            continue
        stat = resolved.stat()
        relative = resolved.relative_to(root)
        videos.append(
            DiscoveredVideo(
                relative_path=relative.as_posix(),
                file_name=resolved.name,
                display_name=_display_name(resolved.stem),
                dataset_name=relative.parts[0] if len(relative.parts) > 1 else None,
                label=infer_label(relative),
                media_type=MEDIA_TYPES[resolved.suffix.lower()],
                size_bytes=stat.st_size,
                file_modified_at=datetime.fromtimestamp(stat.st_mtime, UTC),
            )
        )
    return videos


def infer_label(relative_path: Path) -> OfflineVideoLabel:
    parts = relative_path.with_suffix("").parts
    signals = parts[1:] if len(parts) > 1 else parts
    compact = "".join(re.sub(r"[^a-z0-9]+", "", part.lower()) for part in signals)
    tokens = {
        token
        for part in signals
        for token in re.split(r"[^a-z0-9]+", part.lower())
        if token
    }
    if "nearfall" in compact or "prefall" in compact:
        return OfflineVideoLabel.NEAR_FALL
    if "nonfall" in compact or "nofall" in compact or "adl" in tokens:
        return OfflineVideoLabel.ADL
    if "fall" in tokens or any(token.startswith("fall") for token in tokens):
        return OfflineVideoLabel.FALL
    if tokens.intersection({"daily", "normal", "walking", "sleeping", "sitting"}):
        return OfflineVideoLabel.ADL
    return OfflineVideoLabel.UNKNOWN


def _display_name(stem: str) -> str:
    return re.sub(r"[_-]+", " ", stem).strip() or stem


def to_offline_video_read(video: OfflineVideo) -> OfflineVideoRead:
    return OfflineVideoRead.model_validate(
        {
            **{column.name: getattr(video, column.name) for column in video.__table__.columns},
            "requires_transcoding": (
                Path(video.relative_path).suffix.lower() not in BROWSER_NATIVE_EXTENSIONS
            ),
        }
    )


def transcode_video(source: Path, target: Path, timeout_seconds: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.stem}-{uuid.uuid4().hex}.tmp.mp4")
    command = [
        get_ffmpeg_exe(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-sn",
        "-dn",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(temporary),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, "CREATE_NO_WINDOW")
                else 0
            ),
        )
        if result.returncode != 0 or not temporary.is_file():
            detail = (
                result.stderr.strip().splitlines()[-1]
                if result.stderr.strip()
                else "unknown error"
            )
            raise OfflineVideoTranscodeError(
                f"FFmpeg could not prepare this video: {detail[:240]}"
            )
        temporary.replace(target)
    except subprocess.TimeoutExpired as exc:
        raise OfflineVideoTranscodeError(
            f"Video conversion exceeded {timeout_seconds} seconds"
        ) from exc
    finally:
        temporary.unlink(missing_ok=True)
