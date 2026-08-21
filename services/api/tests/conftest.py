from collections.abc import AsyncIterator

import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User, UserRole

TEST_PASSWORD = "correct-horse-battery-staple"


@pytest_asyncio.fixture
async def app(tmp_path):
    database_path = (tmp_path / "test.db").as_posix()
    offline_video_root = tmp_path / "offline-videos"
    offline_video_cache_root = tmp_path / "offline-video-cache"
    settings = Settings(
        _env_file=None,
        app_env="test",
        jwt_secret="test-secret-that-is-longer-than-thirty-two-characters",
        access_token_expire_minutes=5,
        refresh_token_expire_days=1,
        database_url=f"sqlite+aiosqlite:///{database_path}",
        auto_create_tables=True,
        redis_url="redis://127.0.0.1:1/0",
        minio_endpoint="127.0.0.1:1",
        offline_video_root=offline_video_root,
        offline_video_cache_root=offline_video_cache_root,
    )
    application = create_app(settings)
    async with LifespanManager(application):
        async with application.state.session_factory() as session:
            session.add(
                User(
                    username="admin",
                    password_hash=hash_password(TEST_PASSWORD),
                    display_name="测试管理员",
                    role=UserRole.ADMIN,
                    is_active=True,
                )
            )
            session.add(
                User(
                    username="caregiver",
                    password_hash=hash_password(TEST_PASSWORD),
                    display_name="测试护理人员",
                    role=UserRole.CAREGIVER,
                    is_active=True,
                )
            )
            session.add(
                User(
                    username="disabled",
                    password_hash=hash_password(TEST_PASSWORD),
                    display_name="停用用户",
                    role=UserRole.FAMILY,
                    is_active=False,
                )
            )
            await session.commit()
        yield application


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
