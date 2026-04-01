"""Integration tests for database repository."""
import asyncio
from pathlib import Path

from sqlalchemy import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db import Base, Repository, SwipeAction


async def test_repository():
    """Test repository CRUD operations."""
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        engine = create_async_engine(db_url, echo=False, future=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            repo = Repository(session)

            image = await repo.save_image(
                image_url="https://example.com/image1.jpg",
                md5="abc123",
                tags="cat dog landscape",
            )
            assert image.id is not None
            assert image.md5 == "abc123"

            swipe = await repo.save_swipe(
                image_id=image.id,
                action=SwipeAction.LIKE,
                tags="cat dog landscape",
            )
            assert swipe.id is not None
            assert swipe.action == SwipeAction.LIKE

            stats = await repo.get_swipe_stats()
            assert stats["total_swipes"] == 1
            assert stats["total_likes"] == 1

            swipe_list = await repo.get_swipes()
            assert len(swipe_list) == 1
            assert swipe_list[0].action == SwipeAction.LIKE

            print("✓ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_repository())
