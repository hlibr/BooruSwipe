"""Tests for source-specific sorting and selection behavior."""

import asyncio
from typing import Any

import pytest

from booruswipe.booru_sources import get_score_sort_tag, get_search_sort_tag
from booruswipe.gelbooru.client import DanbooruClient, E621Client, GelbooruClient
from booruswipe.gelbooru.models import Image
from booruswipe.selection import (
    compact_recent_tag_scores,
    compact_recent_tag_scores_split,
    decay_value,
    filter_non_animated,
    pick_best_scored_unseen,
    pick_first_non_animated,
    pick_first_unseen,
    score_image,
)


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


async def _capture_search_tags(client: Any, tags: list[str], response: Any, **search_kwargs: Any):
    """Patch a client's request layer and capture the built query string."""
    captured: dict[str, Any] = {}

    async def fake_request(**params):
        captured["params"] = params
        return response

    client._request = fake_request  # type: ignore[attr-defined]
    images = await client.search_images(tags, **search_kwargs)
    return captured["params"]["tags"], images


def test_score_sort_tags_match_source():
    """Each source should use the correct descending-score sort tag."""
    assert get_score_sort_tag("gelbooru") == "sort:score"
    assert get_score_sort_tag("danbooru") == "order:score"
    assert get_score_sort_tag("e621") == "order:score"
    assert get_search_sort_tag("gelbooru", "score") == "sort:score"
    assert get_search_sort_tag("danbooru", "score") == "order:score"
    assert get_search_sort_tag("e621", "score") == "order:score"


def test_random_sort_tags_match_source():
    """Each source should use the correct random sort tag."""
    assert get_search_sort_tag("gelbooru", "random") == "sort:random"
    assert get_search_sort_tag("danbooru", "random") == "random:1"
    assert get_search_sort_tag("e621", "random") == "order:random"


def test_clients_append_score_sort_tags(monkeypatch):
    """Search queries should include score sorting for non-random queries."""
    monkeypatch.delenv("SKIP_ANIMATED_IMAGES", raising=False)

    async def scenario():
        danbooru_tags, _ = await _capture_search_tags(
            DanbooruClient(),
            ["cat"],
            [{"id": 1, "tag_string": "cat", "file_url": "https://example.com/1.jpg", "file_ext": "jpg"}],
            sort_mode="score",
        )
        gelbooru_tags, _ = await _capture_search_tags(
            GelbooruClient(),
            ["cat"],
            {"post": [{"id": 1, "tag_string": "cat", "file_url": "https://example.com/1.jpg", "file_ext": "jpg"}]},
            sort_mode="score",
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
            sort_mode="score",
        )

        assert danbooru_tags == "cat -animated order:score"
        assert gelbooru_tags == "cat -animated sort:score"
        assert e621_tags == "cat -animated order:score"

    asyncio.run(scenario())


def test_clients_append_random_sort_tags(monkeypatch):
    """Search queries should include random sorting when requested."""
    monkeypatch.delenv("SKIP_ANIMATED_IMAGES", raising=False)

    async def scenario():
        danbooru_tags, _ = await _capture_search_tags(
            DanbooruClient(),
            ["cat"],
            [{"id": 1, "tag_string": "cat", "file_url": "https://example.com/1.jpg", "file_ext": "jpg"}],
            sort_mode="random",
        )
        gelbooru_tags, _ = await _capture_search_tags(
            GelbooruClient(),
            ["cat"],
            {"post": [{"id": 1, "tag_string": "cat", "file_url": "https://example.com/1.jpg", "file_ext": "jpg"}]},
            sort_mode="random",
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
            sort_mode="random",
        )

        assert danbooru_tags == "cat -animated random:1"
        assert gelbooru_tags == "cat -animated sort:random"
        assert e621_tags == "cat -animated order:random"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("client_factory", "response", "expected_query"),
    [
        (
            DanbooruClient,
            [{"id": 1, "tag_string": "cat", "file_url": "https://example.com/1.jpg", "file_ext": "jpg"}],
            "fixed_one fixed_two one two -avoid_one -animated order:score",
        ),
        (
            GelbooruClient,
            {"post": [{"id": 1, "tag_string": "cat", "file_url": "https://example.com/1.jpg", "file_ext": "jpg"}]},
            "fixed_one fixed_two one two -avoid_one -animated sort:score",
        ),
        (
            E621Client,
            {
                "posts": [
                    {
                        "id": 1,
                        "tags": {"general": ["cat"]},
                        "file": {"url": "https://example.com/1.jpg", "ext": "jpg"},
                    }
                ]
            },
            "fixed_one fixed_two one two -avoid_one -animated order:score",
        ),
    ],
)
def test_clients_keep_fixed_tags_outside_search_limit(monkeypatch, client_factory, response, expected_query):
    """Fixed tags should not consume the BOORU_TAGS_PER_SEARCH budget."""
    monkeypatch.setenv("BOORU_TAGS_PER_SEARCH", "2")
    monkeypatch.delenv("SKIP_ANIMATED_IMAGES", raising=False)

    async def scenario():
        query_tags, _ = await _capture_search_tags(
            client_factory(),
            ["one", "two", "three"],
            response,
            sort_mode="score",
            always_include_tags=["fixed_one", "fixed_two"],
            always_include_negative_tags=["avoid_one"],
        )

        assert query_tags == expected_query

    asyncio.run(scenario())


def test_pick_first_unseen_returns_first_unseen_image():
    """The selection helper should preserve the ordering from the search results."""
    images = [_make_image(1), _make_image(2), _make_image(3)]

    assert pick_first_unseen(images, {1, 2}).id == 3
    assert pick_first_unseen(images, {1, 2, 3}) is None


def test_pick_first_non_animated_skips_animated_images():
    """Animated candidates should be skipped before ranking or selection."""
    animated = _make_image(1)
    animated.media_type = "image/gif"
    animated.tags = ["animated"]
    static = _make_image(2)

    assert pick_first_non_animated([animated, static]).id == 2
    assert [image.id for image in filter_non_animated([animated, static])] == [2]


def test_score_image_uses_cumulative_and_recent_weights():
    """Local ranking should combine cumulative and recent tag affinity."""
    image = Image(
        url="https://example.com/1.jpg",
        tags=["cat", "smile"],
        id=1,
        width=100,
        height=100,
        sample=False,
        sample_url="",
        media_type="image",
        directory="",
    )

    score = score_image(
        image,
        cumulative_tag_scores={"cat": 2, "smile": 1},
        recent_tag_scores={"cat": 1, "smile": 2},
    )

    assert score == pytest.approx(7.5)


def test_decay_value_halves_on_half_life_boundary():
    """A score should be cut in half after one half-life worth of swipes."""
    score = decay_value(8.0, age_swipes=30, half_life_swipes=30)

    assert score == pytest.approx(4.0)


def test_decay_value_keeps_recent_scores_near_original():
    """A score with very small swipe age should not lose much weight."""
    score = decay_value(8.0, age_swipes=1, half_life_swipes=30)

    assert score == pytest.approx(8.0, rel=3e-2)


def test_compact_recent_tag_scores_uses_absolute_value_order():
    """Recent tags should be compacted by absolute score, not sign."""
    compacted = compact_recent_tag_scores(
        {
            "small_positive": 2,
            "big_negative": -9,
            "mid_positive": 5,
            "mid_negative": -4,
            "zero": 0,
            "tiny_positive": 1,
        },
        limit=3,
        cumulative_liked_tags={"mid_positive"},
    )

    assert list(compacted.keys()) == ["big_negative", "mid_negative", "small_positive"]
    assert compacted["big_negative"] == -9
    assert compacted["mid_negative"] == -4
    assert compacted["small_positive"] == 2


def test_compact_recent_tag_scores_split_keeps_positive_and_negative_caps():
    """Split mode should keep positive and negative recent tags separately."""
    compacted = compact_recent_tag_scores_split(
        {
            "small_positive": 2,
            "big_negative": -9,
            "mid_positive": 5,
            "mid_negative": -4,
            "zero": 0,
            "tiny_positive": 1,
        },
        positive_limit=2,
        negative_limit=1,
        cumulative_liked_tags={"mid_positive"},
    )

    assert list(compacted.keys()) == ["small_positive", "tiny_positive", "big_negative"]
    assert compacted["small_positive"] == 2
    assert compacted["tiny_positive"] == 1
    assert compacted["big_negative"] == -9


def test_pick_best_scored_unseen_prefers_highest_scoring_candidate():
    """The selector should return the unseen image with the best local score."""
    images = [
        Image(
            url="https://example.com/1.jpg",
            tags=["cat", "smile"],
            id=1,
            width=100,
            height=100,
            sample=False,
            sample_url="",
            media_type="image",
            directory="",
        ),
        Image(
            url="https://example.com/2.jpg",
            tags=["cat"],
            id=2,
            width=100,
            height=100,
            sample=False,
            sample_url="",
            media_type="image",
            directory="",
        ),
        Image(
            url="https://example.com/3.jpg",
            tags=["dog"],
            id=3,
            width=100,
            height=100,
            sample=False,
            sample_url="",
            media_type="image",
            directory="",
        ),
    ]

    best = pick_best_scored_unseen(
        images,
        seen_ids=set(),
        cumulative_tag_scores={"cat": 3, "smile": 1},
        recent_tag_scores={"cat": 1, "smile": 2},
    )

    assert best is not None
    assert best.image.id == 1
    assert best.score == pytest.approx(8.5)


def test_pick_best_scored_unseen_skips_seen_images():
    """Already-seen images should be excluded before scoring."""
    images = [
        _make_image(1, tag="cat"),
        _make_image(2, tag="cat"),
        _make_image(3, tag="dog"),
    ]

    best = pick_best_scored_unseen(
        images,
        seen_ids={1},
        cumulative_tag_scores={"cat": 3},
        recent_tag_scores={"cat": 1},
    )

    assert best is not None
    assert best.image.id == 2
