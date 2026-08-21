import asyncio
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import create_database
from app.core.security import hash_password
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


async def seed_initial_admin() -> None:
    settings = get_settings()
    if not settings.initial_admin_username or not settings.initial_admin_password:
        logger.info("Initial admin is not configured; skipping seed")
        return

    engine, session_factory = create_database(settings)
    try:
        async with session_factory() as session:
            username = settings.initial_admin_username.strip().lower()
            existing = await session.scalar(select(User).where(User.username == username))
            if existing:
                logger.info("Initial admin already exists; password was not changed")
                return
            session.add(
                User(
                    username=username,
                    password_hash=hash_password(settings.initial_admin_password),
                    display_name="系统管理员",
                    role=UserRole.ADMIN,
                    is_active=True,
                )
            )
            await session.commit()
            logger.info("Initial admin created")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_initial_admin())

