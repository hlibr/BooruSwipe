"""Integration tests for the database repository."""

import asyncio
from pathlib import Path

from booruswipe.db.repository import Repository


def test_repository_persists_swipes_and_tag_scores(tmp_path: Path):
    """Test current repository CRUD and aggregate behavior."""
    async def scenario():
        db_path = tmp_path / "test.db"
        repo = Repository(str(db_path))
        await repo.init_db()

        try:
            await repo.save_swipe(
                booru="gelbooru",
                image_id="123",
                post_url="https://gelbooru.com/index.php?page=post&s=view&id=123",
                file_url="https://img.example.com/123.jpg",
                tags=["cat", "smile"],
                liked=True,
                weight=2,
            )
            await repo.update_tag_count("cat", liked=True, weight=2)
            await repo.update_tag_count("smile", liked=True, weight=2)

            await repo.save_swipe(
                booru="gelbooru",
                image_id="124",
                post_url="https://gelbooru.com/index.php?page=post&s=view&id=124",
                file_url="https://img.example.com/124.jpg",
                tags=["cat", "gore"],
                liked=False,
                weight=1,
            )
            await repo.update_tag_count("cat", liked=False, weight=1)
            await repo.update_tag_count("gore", liked=False, weight=1)

            assert await repo.get_total_swipe_count() == 2

            swipes = await repo.get_swipes()
            assert len(swipes) == 2
            assert swipes[0].image_id == "124"
            assert swipes[0].weight == 1
            assert swipes[1].image_id == "123"
            assert swipes[1].weight == 2

            tag_counts = await repo.get_tag_counts()
            assert tag_counts["cat"]["liked_count"] == 2
            assert tag_counts["cat"]["disliked_count"] == 1
            assert tag_counts["smile"]["liked_count"] == 2
            assert tag_counts["gore"]["disliked_count"] == 1

            recent_scores = await repo.get_recent_tag_scores(limit=2)
            assert recent_scores["cat"] == 1
            assert recent_scores["smile"] == 2
            assert recent_scores["gore"] == -1
        finally:
            await repo.close()

    asyncio.run(scenario())


def test_repository_filters_out_double_liked_swiped_ids(tmp_path: Path):
    """Double-liked IDs should be excluded from filtered swiped IDs by default."""
    async def scenario():
        db_path = tmp_path / "test_filter.db"
        repo = Repository(str(db_path))
        await repo.init_db()

        try:
            await repo.add_swiped_image(101, liked=True)
            await repo.add_swiped_image(102, liked=False)
            await repo.add_double_liked_image(101)

            filtered = await repo.get_filtered_swiped_image_ids()
            unfiltered = await repo.get_filtered_swiped_image_ids(exclude_double_liked=False)

            assert filtered == {102}
            assert unfiltered == {101, 102}
        finally:
            await repo.close()

    asyncio.run(scenario())


def test_repository_get_or_create_profile_is_idempotent(tmp_path: Path):
    """Fetching the profile multiple times should reuse the same record."""
    async def scenario():
        db_path = tmp_path / "test_profile.db"
        repo = Repository(str(db_path))
        await repo.init_db()

        try:
            first = await repo.get_or_create_profile()
            second = await repo.get_or_create_profile()

            assert first.id == second.id
        finally:
            await repo.close()

    asyncio.run(scenario())


def test_repository_persists_app_settings(tmp_path: Path):
    """App settings should round-trip through the dedicated settings table."""
    async def scenario():
        db_path = tmp_path / "test_settings.db"
        repo = Repository(str(db_path))
        await repo.init_db()

        try:
            await repo.update_app_settings(
                {
                    "always_include_tags": "cat, blue_eyes",
                    "always_include_negative_tags": "blurry, lowres",
                }
            )

            settings = await repo.get_or_create_app_settings()
            assert settings.always_include_tags == "cat, blue_eyes"
            assert settings.always_include_negative_tags == "blurry, lowres"
        finally:
            await repo.close()

    asyncio.run(scenario())


def test_repository_seeds_app_settings_without_overwriting_existing_values(tmp_path: Path):
    """Seed values should only fill blank database settings."""
    async def scenario():
        db_path = tmp_path / "test_settings_seed.db"
        repo = Repository(str(db_path))
        await repo.init_db()

        try:
            await repo.update_app_settings(
                {
                    "always_include_tags": "existing-tag",
                }
            )

            await repo.seed_app_settings(
                {
                    "always_include_tags": "legacy-tag",
                    "always_include_negative_tags": "legacy-negative",
                }
            )

            settings = await repo.get_or_create_app_settings()
            assert settings.always_include_tags == "existing-tag"
            assert settings.always_include_negative_tags == "legacy-negative"
        finally:
            await repo.close()

    asyncio.run(scenario())
