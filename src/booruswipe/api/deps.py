"""Dependency injection for API routes."""

import logging
from typing import AsyncGenerator, Optional

from fastapi import HTTPException, status

from booruswipe.booru_sources import get_booru_source
from booruswipe.db.repository import Repository
from booruswipe.gelbooru.client import BooruClient, DanbooruClient, E621Client, GelbooruClient
from booruswipe.llm.client import LLMClient
from booruswipe.llm.preference_learner import PreferenceLearner

logger = logging.getLogger(__name__)


_repository: Optional[Repository] = None
_danbooru_client: Optional[DanbooruClient] = None
_gelbooru_client: Optional[GelbooruClient] = None
_e621_client: Optional[E621Client] = None
_llm_client: Optional[LLMClient] = None
_preference_learner: Optional[PreferenceLearner] = None
_verbose_mode: bool = False


def set_dependencies(
    repository: Repository,
    danbooru_client: Optional[DanbooruClient] = None,
    gelbooru_client: Optional[GelbooruClient] = None,
    e621_client: Optional[E621Client] = None,
    llm_client: Optional[LLMClient] = None,
) -> None:
    """Set up global dependencies for the API.
    
    Args:
        repository: Database repository instance
        danbooru_client: Danbooru API client instance (if using danbooru)
        gelbooru_client: Gelbooru API client instance (if using gelbooru)
        e621_client: e621 API client instance (if using e621)
        llm_client: Optional LLM client for preference learning
    """
    global _repository, _danbooru_client, _gelbooru_client, _e621_client, _llm_client, _preference_learner
    _repository = repository
    _danbooru_client = danbooru_client
    _gelbooru_client = gelbooru_client
    _e621_client = e621_client
    _llm_client = llm_client
    if llm_client:
        _preference_learner = PreferenceLearner(llm_client, _verbose_mode)
    else:
        _preference_learner = None
        if _verbose_mode:
            print("LLM client not configured - preference learning disabled")


def set_verbose_mode(verbose: bool) -> None:
    """Set verbose logging mode.
    
    Args:
        verbose: Whether to enable verbose logging
    """
    global _verbose_mode
    _verbose_mode = verbose


def is_verbose_mode() -> bool:
    """Check if verbose logging is enabled.
    
    Returns:
        True if verbose mode is enabled
    """
    return _verbose_mode


async def get_repository() -> AsyncGenerator[Repository, None]:
    """Get database repository instance."""
    if _repository is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Repository not initialized",
        )
    yield _repository


async def get_booru_client() -> AsyncGenerator[BooruClient, None]:
    """Get the configured booru API client instance."""
    source = get_booru_source()
    if source == "gelbooru":
        client = _gelbooru_client
    elif source == "danbooru":
        client = _danbooru_client
    elif source == "e621":
        client = _e621_client
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unsupported BOORU_SOURCE: {source}",
        )

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No booru client initialized",
        )
    yield client


def check_booru_client(client: BooruClient) -> None:
    """Check if booru API client is configured.
    
    Raises HTTPException if client is not available.
    """
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Booru API client not configured",
        )


async def get_llm_client() -> AsyncGenerator[LLMClient, None]:
    """Get LLM client instance."""
    if _llm_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM client not initialized",
        )
    yield _llm_client


async def get_preference_learner() -> PreferenceLearner:
    """Get preference learner instance. Raises error if not initialized."""
    if _preference_learner is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Preference learner not initialized",
        )
    return _preference_learner


async def get_optional_preference_learner() -> Optional[PreferenceLearner]:
    """Get preference learner instance. Returns None if not initialized."""
    return _preference_learner
