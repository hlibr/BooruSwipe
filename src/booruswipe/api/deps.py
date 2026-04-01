"""Dependency injection for API routes."""

import logging
from typing import AsyncGenerator, Optional, Union

from fastapi import Depends, HTTPException, status

from booruswipe.db.repository import Repository
from booruswipe.gelbooru.client import DanbooruClient, GelbooruClient
from booruswipe.llm.client import LLMClient
from booruswipe.llm.preference_learner import PreferenceLearner

logger = logging.getLogger(__name__)


_repository: Optional[Repository] = None
_danbooru_client: Optional[DanbooruClient] = None
_gelbooru_client: Optional[GelbooruClient] = None
_llm_client: Optional[LLMClient] = None
_preference_learner: Optional[PreferenceLearner] = None
_verbose_mode: bool = False


def set_dependencies(
    repository: Repository,
    danbooru_client: Optional[DanbooruClient] = None,
    gelbooru_client: Optional[GelbooruClient] = None,
    llm_client: Optional[LLMClient] = None,
) -> None:
    """Set up global dependencies for the API.
    
    Args:
        repository: Database repository instance
        danbooru_client: Danbooru API client instance (if using danbooru)
        gelbooru_client: Gelbooru API client instance (if using gelbooru)
        llm_client: Optional LLM client for preference learning
    """
    global _repository, _danbooru_client, _gelbooru_client, _llm_client, _preference_learner
    _repository = repository
    _danbooru_client = danbooru_client
    _gelbooru_client = gelbooru_client
    _llm_client = llm_client
    if llm_client:
        _preference_learner = PreferenceLearner(llm_client, _verbose_mode)
    elif _verbose_mode:
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


async def get_booru_client() -> AsyncGenerator[Union[DanbooruClient, GelbooruClient], None]:
    """Get the configured booru API client instance."""
    if _danbooru_client is None and _gelbooru_client is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No booru client initialized",
        )
    yield _danbooru_client or _gelbooru_client


def check_booru_client(client: Union[DanbooruClient, GelbooruClient]) -> None:
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
