"""Tests for source-specific sorting and selection behavior."""

import asyncio
from typing import Any

from booruswipe.booru_sources import get_score_sort_tag
from booruswipe.gelbooru.client import DanbooruClient, E621Client, GelbooruClient
from booruswipe.gelbooru.models import Image
from booruswipe.selection import pick_first_unseen


def _make_image(image_id: int, tag: str = "cat") -> Image:
    """Create a minimal Image for selection tests."""
    return Image(
        url=f"https://example.com/{image_id}.jpg",
        tags=[tag],
        id=image_id,
        width=100,
        height=100,
        sample=False,
        sample_url="",
        media_type="image",
        directory="",
    )


async def _capture_search_tags(client: Any, tags: list[str], response: Any):
    """Patch a client's request layer and capture the built query string."""
    captured: dict[str, Any] = {}

    async def fake_request(**params):
        captured["params"] = params
        return response

    client._request = fake_request  # type: ignore[attr-defined]
    images = await client.search_images(tags)
    return captured["params"]["tags"], images


def test_score_sort_tags_match_source():
    """Each source should use the correct descending-score sort tag."""
    assert get_score_sort_tag("gelbooru") == "sort:score"
    assert get_score_sort_tag("danbooru") == "order:score"
    assert get_score_sort_tag("e621") == "order:score"


def test_clients_append_score_sort_tags():
    """Search queries should include score sorting for non-random queries."""

    async def scenario():
        danbooru_tags, _ = await _capture_search_tags(
            DanbooruClient(),
            ["cat"],
            [{"id": 1, "tag_string": "cat", "file_url": "https://example.com/1.jpg", "file_ext": "jpg"}],
        )
        gelbooru_tags, _ = await _capture_search_tags(
            GelbooruClient(),
            ["cat"],
            {"post": [{"id": 1, "tag_string": "cat", "file_url": "https://example.com/1.jpg", "file_ext": "jpg"}]},
        )
        e621_tags, _ = await _capture_search_tags(
            E621Client(),
            ["cat"],
            {
                "posts": [
                    {
                        "id": 1,
                        "tags": {"general": ["cat"]},
                        "file": {"url": "https://example.com/1.jpg", "ext": "jpg"},
                    }
                ]
            },
        )

        assert danbooru_tags == "cat order:score"
        assert gelbooru_tags == "cat sort:score"
        assert e621_tags == "cat order:score"

    asyncio.run(scenario())


def test_pick_first_unseen_returns_first_unseen_image():
    """The selection helper should preserve the ordering from the search results."""
    images = [_make_image(1), _make_image(2), _make_image(3)]

    assert pick_first_unseen(images, {1, 2}).id == 3
    assert pick_first_unseen(images, {1, 2, 3}) is None
