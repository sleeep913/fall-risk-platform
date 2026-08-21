from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings


def create_database(
    settings: Settings,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine_options: dict[str, object] = {
        "pool_pre_ping": True,
        "echo": settings.app_env == "development" and settings.log_level == "DEBUG",
    }
    if settings.database_url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}

    engine = create_async_engine(settings.database_url, **engine_options)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings

