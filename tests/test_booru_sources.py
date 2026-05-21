"""Tests for booru source helpers."""

from booruswipe.booru_sources import get_post_url, get_random_search_tag


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
