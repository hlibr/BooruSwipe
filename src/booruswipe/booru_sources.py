"""Helpers for working with configured booru sources."""

import os

SUPPORTED_BOORU_SOURCES = {"gelbooru", "danbooru", "e621"}
SUPPORTED_BOORU_SEARCH_SORT_MODES = {"score", "random"}


def get_booru_source() -> str:
    """Return the configured booru source name."""
    return os.getenv("BOORU_SOURCE", "gelbooru").lower()


def get_random_search_tag(source: str | None = None) -> str:
    """Return the source-specific query tag used for random selection."""
    booru_source = (source or get_booru_source()).lower()
    if booru_source == "gelbooru":
        return "sort:random"
    if booru_source == "e621":
        return "order:random"
    return "random:1"


def get_score_sort_tag(source: str | None = None) -> str:
    """Return the source-specific query tag used to sort by score descending."""
    booru_source = (source or get_booru_source()).lower()
    if booru_source == "gelbooru":
        return "sort:score"
    return "order:score"


def get_search_sort_mode() -> str:
    """Return the configured search sort mode."""
    sort_mode = os.getenv("BOORU_SEARCH_SORT_MODE", "score").lower()
    if sort_mode not in SUPPORTED_BOORU_SEARCH_SORT_MODES:
        raise ValueError(f"Unsupported BOORU_SEARCH_SORT_MODE: {sort_mode}")
    return sort_mode


def get_search_sort_tag(source: str | None = None, sort_mode: str = "score") -> str:
    """Return the source-specific query tag for the configured sort mode."""
    normalized_sort_mode = sort_mode.lower()
    if normalized_sort_mode == "score":
        return get_score_sort_tag(source)
    if normalized_sort_mode == "random":
        return get_random_search_tag(source)
    raise ValueError(f"Unsupported search sort mode: {sort_mode}")


def get_post_url(source: str, image_id: int) -> str:
    """Build the canonical post URL for a booru source."""
    booru_source = source.lower()
    if booru_source == "gelbooru":
        return f"https://gelbooru.com/index.php?page=post&s=view&id={image_id}"
    if booru_source == "e621":
        return f"https://e621.net/posts/{image_id}"
    return f"https://danbooru.donmai.us/posts/{image_id}"
