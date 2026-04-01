"""Tests for LLM integration."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from booruswipe.db.models import Swipe
from booruswipe.llm.client import LLMClient
from booruswipe.llm.preference_learner import PreferenceLearner


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = AsyncMock(spec=LLMClient)
    return client


@pytest.fixture
def sample_swipe_history():
    """Create sample swipe history for testing."""
    history = []
    for i in range(10):
        liked = i < 7
        swipe = Swipe(
            id=i + 1,
            booru="gelbooru",
            image_id=str(i + 1),
            post_url=f"https://gelbooru.com/index.php?page=post&s=view&id={i + 1}",
            file_url=f"https://img.gelbooru.com/{i + 1}.jpg",
            tags=["tag1", "tag2", "tag3", "popular", "favorite"] if liked else ["tag4", "tag5", "tag6", "unpopular", "boring"],
            liked=liked,
        )
        history.append(swipe)
    return history


@pytest.mark.asyncio
async def test_analyze_preferences_with_mock_llm(mock_llm_client, sample_swipe_history):
    """Test preference analysis with mocked LLM response."""
    expected_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "liked_tags": ["tag1", "tag2", "tag3"],
                        "disliked_tags": ["tag4", "tag5"],
                        "preferences_summary": "User prefers popular and favorite tags",
                        "recommended_search_tags": ["tag1", "tag2", "tag3", "popular", "favorite"],
                    })
                }
            }
        ]
    }

    mock_llm_client.chat_completion.return_value = expected_response

    learner = PreferenceLearner(mock_llm_client)
    profile = await learner.analyze_preferences(sample_swipe_history)

    assert profile.total_swipes == 10
    assert profile.total_likes == 7
    assert profile.total_dislikes == 3
    assert "tag1" in profile.liked_tags
    assert profile.preferences_summary is not None
    assert len(profile.recommended_search_tags) > 0


@pytest.mark.asyncio
async def test_analyze_preferences_empty_history(mock_llm_client):
    """Test preference analysis with empty history."""
    learner = PreferenceLearner(mock_llm_client)
    profile = await learner.analyze_preferences([])

    assert profile.total_swipes == 0
    assert profile.total_likes == 0
    assert profile.total_dislikes == 0
    assert profile.liked_tags == []
    assert profile.disliked_tags == []


@pytest.mark.asyncio
async def test_generate_search_query(mock_llm_client, sample_swipe_history):
    """Test search query generation."""
    expected_response = {
        "choices": [
            {"message": {"content": json.dumps({
                "liked_tags": ["tag1", "tag2"],
                "disliked_tags": ["tag3"],
                "preferences_summary": "Test summary",
                "recommended_search_tags": ["tag1", "tag2"],
            })}}
        ]
    }

    mock_llm_client.chat_completion.return_value = expected_response

    learner = PreferenceLearner(mock_llm_client)
    profile = await learner.analyze_preferences(sample_swipe_history)
    query = await learner.generate_search_query(profile)

    assert isinstance(query, list)
    assert len(query) > 0
