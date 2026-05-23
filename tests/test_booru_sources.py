"""Tests for booru source helpers."""

from booruswipe.booru_sources import (
    get_llm_recent_mode,
    get_post_url,
    get_random_search_tag,
    get_skip_animated_images,
)


def test_random_search_tags_match_source():
    """Each supported source should map to its expected random query tag."""
    assert get_random_search_tag("gelbooru") == "sort:random"
    assert get_random_search_tag("danbooru") == "random:1"
    assert get_random_search_tag("e621") == "order:random"


def test_post_urls_match_source():
    """Each supported source should generate the correct post URL."""
    assert get_post_url("gelbooru", 123) == "https://gelbooru.com/index.php?page=post&s=view&id=123"
    assert get_post_url("danbooru", 123) == "https://danbooru.donmai.us/posts/123"
    assert get_post_url("e621", 123) == "https://e621.net/posts/123"


def test_skip_animated_images_defaults_to_true(monkeypatch):
    """Animated images should be skipped unless explicitly disabled."""
    monkeypatch.delenv("SKIP_ANIMATED_IMAGES", raising=False)

    assert get_skip_animated_images() is True


def test_skip_animated_images_can_be_disabled(monkeypatch):
    """The animated-image filter should remain configurable."""
    monkeypatch.setenv("SKIP_ANIMATED_IMAGES", "false")

    assert get_skip_animated_images() is False


def test_llm_recent_mode_defaults_to_split(monkeypatch):
    """Recent tag compaction should default to split mode."""
    monkeypatch.delenv("LLM_RECENT_MODE", raising=False)

    assert get_llm_recent_mode() == "split"


def test_llm_recent_mode_can_be_absolute(monkeypatch):
    """The recent compaction mode should remain configurable."""
    monkeypatch.setenv("LLM_RECENT_MODE", "absolute")

    assert get_llm_recent_mode() == "absolute"
