"""Integration tests for the database repository."""

from pathlib import Path

import pytest

from booruswipe.db.repository import Repository


@pytest.mark.asyncio
async def test_repository_persists_swipes_and_tag_scores(tmp_path: Path):
    """Test current repository CRUD and aggregate behavior."""
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
