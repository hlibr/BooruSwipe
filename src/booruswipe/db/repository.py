"""Repository module for CRUD operations."""
import logging
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .database import Base
from .models import PreferenceProfile, Swipe, TagCount, SwipedImage, DoubleLikedImage

logger = logging.getLogger(__name__)

def log_startup(msg: str):
    logging.info(msg, extra={"category": "STARTUP"})

def log_error(msg: str):
    logging.error(msg, extra={"category": "ERROR"})


class Repository:
    """Repository for database operations."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.home() / ".booruswipe" / "booruswipe.db")
        
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        db_url = f"sqlite+aiosqlite:///{db_path}"
        self._engine = create_async_engine(db_url, echo=False, future=True)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._session: Optional[AsyncSession] = None

    @property
    def async_sessionmaker(self):
        """Expose sessionmaker for creating independent sessions."""
        return self._session_factory

    async def init_db(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            existing_columns = {
                row[1]
                for row in (await conn.execute(text("PRAGMA table_info(swipes)"))).fetchall()
            }
            if "weight" not in existing_columns:
                await conn.execute(
                    text("ALTER TABLE swipes ADD COLUMN weight INTEGER NOT NULL DEFAULT 1")
                )
        log_startup("Database initialized successfully")

    async def save_swipe(
        self,
        booru: str,
        image_id: str,
        post_url: str,
        file_url: str,
        tags: List[str],
        liked: bool,
        weight: int = 1,
    ) -> Swipe:
        async with self.async_sessionmaker() as session:
            try:
                swipe = Swipe(
                    booru=booru,
                    image_id=image_id,
                    post_url=post_url,
                    file_url=file_url,
                    tags=tags,
                    liked=liked,
                    weight=weight,
                )
                session.add(swipe)
                await session.commit()
                return swipe
            except Exception:
                await session.rollback()
                raise

    async def get_swipes(
        self,
        booru: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Swipe]:
        async with self.async_sessionmaker() as session:
            stmt = select(Swipe).order_by(Swipe.timestamp.desc()).limit(limit).offset(offset)
            if booru:
                stmt = stmt.where(Swipe.booru == booru)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_or_create_profile(self, session: Optional[AsyncSession] = None) -> PreferenceProfile:
        if session is not None:
            return await self._get_or_create_profile_inner(session)
        async with self.async_sessionmaker() as session:
            return await self._get_or_create_profile_inner(session)

    async def _get_or_create_profile_inner(self, session: AsyncSession) -> PreferenceProfile:
        try:
            stmt = select(PreferenceProfile).limit(1)
            result = await session.execute(stmt)
            profile = result.scalar_one_or_none()
            
            if profile is None:
                profile = PreferenceProfile()
                session.add(profile)
                await session.commit()
                await session.refresh(profile)
            return profile
        except Exception:
            await session.rollback()
            raise

    async def save_profile(self, session: Optional[AsyncSession] = None, profile: Optional[PreferenceProfile] = None) -> None:
        if session is not None:
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            return
        async with self.async_sessionmaker() as session:
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def get_total_swipe_count(self) -> int:
        async with self.async_sessionmaker() as session:
            from sqlalchemy import func
            stmt = select(func.count()).select_from(Swipe)
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def update_tag_count(self, tag: str, liked: bool, weight: int = 1) -> None:
        async with self.async_sessionmaker() as session:
            try:
                from sqlalchemy.dialects.sqlite import insert as sqlite_insert
                
                stmt = sqlite_insert(TagCount).values(
                    tag=tag,
                    liked_count=weight if liked else 0,
                    disliked_count=0 if liked else weight,
                ).on_conflict_do_update(
                    index_elements=["tag"],
                    set_={
                        "liked_count": TagCount.liked_count + (weight if liked else 0),
                        "disliked_count": TagCount.disliked_count + (0 if liked else weight),
                    },
                )
                await session.execute(stmt)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def add_swiped_image(self, image_id: int, liked: bool) -> None:
        """Record that user swiped this image"""
        async with self.async_sessionmaker() as session:
            try:
                from sqlalchemy.dialects.sqlite import insert as sqlite_insert
                
                stmt = sqlite_insert(SwipedImage).values(
                    image_id=image_id,
                    liked=liked,
                ).on_conflict_do_nothing()
                await session.execute(stmt)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def get_swiped_image_ids(self, limit: int = 1000) -> set[int]:
        """Get last N swiped image IDs for filtering"""
        async with self.async_sessionmaker() as session:
            from sqlalchemy import select
            
            result = await session.execute(
                select(SwipedImage.image_id)
                .order_by(SwipedImage.swiped_at.desc())
                .limit(limit)
            )
            return set(result.scalars().all())

    async def add_double_liked_image(self, image_id: int) -> None:
        """Add image to double-liked list (never ignore)"""
        async with self.async_sessionmaker() as session:
            try:
                from sqlalchemy.dialects.sqlite import insert as sqlite_insert
                
                stmt = sqlite_insert(DoubleLikedImage).values(
                    image_id=image_id,
                ).on_conflict_do_nothing()
                await session.execute(stmt)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def get_double_liked_image_ids(self) -> set[int]:
        """Get all double-liked image IDs"""
        async with self.async_sessionmaker() as session:
            from sqlalchemy import select
            result = await session.execute(select(DoubleLikedImage.image_id))
            return set(result.scalars().all())

    async def get_filtered_swiped_image_ids(
        self,
        limit: int = 1000,
        exclude_double_liked: bool = True
    ) -> set[int]:
        """Get swiped image IDs, optionally excluding double-liked images.
        
        Args:
            limit: Maximum number of IDs to return
            exclude_double_liked: If True, double-liked images are NOT in the returned set
                                 (they can be shown again). If False, returns all swiped images.
        """
        async with self.async_sessionmaker() as session:
            from sqlalchemy import select
            swiped_stmt = select(SwipedImage.image_id).order_by(SwipedImage.swiped_at.desc()).limit(limit)
            swiped_ids = set((await session.execute(swiped_stmt)).scalars().all())
            
            if exclude_double_liked:
                double_liked_stmt = select(DoubleLikedImage.image_id)
                double_liked_ids = set((await session.execute(double_liked_stmt)).scalars().all())
                return swiped_ids - double_liked_ids
            else:
                return swiped_ids

    async def migrate_existing_swipes(self) -> int:
        """Migrate existing swipes to swiped_images table if empty"""
        async with self.async_sessionmaker() as session:
            from sqlalchemy import select, func
            
            swiped_count_stmt = select(func.count()).select_from(SwipedImage)
            swiped_count_result = await session.execute(swiped_count_stmt)
            swiped_count = swiped_count_result.scalar() or 0
            
            if swiped_count > 0:
                return 0
            
            swipe_count_stmt = select(func.count()).select_from(Swipe)
            swipe_count_result = await session.execute(swipe_count_stmt)
            swipe_count = swipe_count_result.scalar() or 0
            
            if swipe_count == 0:
                return 0
            
            result = await session.execute(select(Swipe))
            swipes = result.scalars().all()
            
            migrated = 0
            for swipe in swipes:
                try:
                    await self.add_swiped_image(int(swipe.image_id), swipe.liked)
                    migrated += 1
                except (ValueError, TypeError):
                    continue
            
            log_startup(f"Migrated {migrated} existing swipes to swiped_images table")
            return migrated

    async def get_tag_counts(self) -> dict:
        async with self.async_sessionmaker() as session:
            stmt = select(TagCount)
            result = await session.execute(stmt)
            tag_counts = result.scalars().all()
            
            return {
                tc.tag: {
                    "liked_count": tc.liked_count,
                    "disliked_count": tc.disliked_count,
                    "last_updated": tc.last_updated,
                }
                for tc in tag_counts
            }

    async def get_tag_counts_for_llm(self, session: Optional[AsyncSession] = None, limit: int = 100, min_absolute_count: int = 2) -> dict:
        if session is not None:
            return await self._get_tag_counts_for_llm_inner(session, limit, min_absolute_count)
        async with self.async_sessionmaker() as session:
            return await self._get_tag_counts_for_llm_inner(session, limit, min_absolute_count)

    async def _get_tag_counts_for_llm_inner(self, session: AsyncSession, limit: int = 100, min_absolute_count: int = 2) -> dict:
        
        half_limit = limit // 2
        
        top_positive = select(TagCount).order_by(
            (TagCount.liked_count - TagCount.disliked_count).desc()
        ).limit(half_limit)
        
        top_negative = select(TagCount).order_by(
            (TagCount.liked_count - TagCount.disliked_count).asc()
        ).limit(half_limit)
        
        result_positive = await session.execute(top_positive)
        positive_tags = result_positive.scalars().all()
        
        result_negative = await session.execute(top_negative)
        negative_tags = result_negative.scalars().all()
        
        tag_counts = list(positive_tags) + list(negative_tags)
        
        return {
            tc.tag: {
                "liked_count": tc.liked_count,
                "disliked_count": tc.disliked_count,
                "net_count": tc.liked_count - tc.disliked_count,
            }
            for tc in tag_counts
            # if abs(tc.liked_count - tc.disliked_count) >= min_absolute_count
        }

    async def get_top_liked_tags(self, limit: int = 2) -> List[str]:
        async with self.async_sessionmaker() as session:
            stmt = select(TagCount).order_by(
                (TagCount.liked_count - TagCount.disliked_count).desc()
            ).limit(limit)
            result = await session.execute(stmt)
            tag_counts = result.scalars().all()
            return [tc.tag for tc in tag_counts if tc.liked_count > 0]

    async def get_image_by_id(self, image_id: int) -> Optional[Swipe]:
        """Get image record by ID for proxying."""
        async with self.async_sessionmaker() as session:
            from sqlalchemy import select
            stmt = select(Swipe).where(Swipe.image_id == str(image_id)).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_recent_tag_scores(self, limit: int = 10) -> dict[str, int]:
        """Get rolling tag scores from last N swipes."""
        async with self.async_sessionmaker() as session:
            stmt = select(Swipe).order_by(Swipe.timestamp.desc()).limit(limit)
            result = await session.execute(stmt)
            recent_swipes = result.scalars().all()
            
            tag_scores: dict[str, int] = {}
            for swipe in recent_swipes:
                score = swipe.weight if swipe.liked else -swipe.weight
                for tag in swipe.tags:
                    tag_scores[tag] = tag_scores.get(tag, 0) + score
            
            return tag_scores

    async def close(self) -> None:
        await self._engine.dispose()
