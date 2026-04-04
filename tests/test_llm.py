"""Tests for LLM integration."""

import json
from unittest.mock import AsyncMock

import pytest

from booruswipe.llm.client import LLMClient
from booruswipe.llm.preference_learner import PreferenceLearner


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = AsyncMock(spec=LLMClient)
    return client


@pytest.fixture
def sample_tag_stats():
    """Create sample aggregate tag stats for testing."""
    return {
        "tag1": {"liked_count": 7, "disliked_count": 1, "net_count": 6},
        "tag2": {"liked_count": 5, "disliked_count": 0, "net_count": 5},
        "popular": {"liked_count": 4, "disliked_count": 0, "net_count": 4},
        "tag4": {"liked_count": 0, "disliked_count": 3, "net_count": -3},
        "boring": {"liked_count": 1, "disliked_count": 4, "net_count": -3},
    }


@pytest.mark.asyncio
async def test_analyze_preferences_with_mock_llm(mock_llm_client, sample_tag_stats):
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
    profile = await learner.analyze_preferences(
        sample_tag_stats,
        tag_limit=5,
        recent_tag_scores={"tag1": 2, "boring": -1},
    )

    assert profile.liked_tags == ["tag1", "tag2", "tag3"]
    assert profile.disliked_tags == ["tag4", "tag5"]
    assert profile.preferences_summary == "User prefers popular and favorite tags"
    assert profile.recommended_search_tags == ["tag1", "tag2", "tag3", "popular", "favorite"]


@pytest.mark.asyncio
async def test_analyze_preferences_empty_history(mock_llm_client):
    """Test preference analysis with empty history."""
    learner = PreferenceLearner(mock_llm_client)
    profile = await learner.analyze_preferences({})

    assert profile.total_swipes == 0
    assert profile.total_likes == 0
    assert profile.total_dislikes == 0
    assert profile.liked_tags == []
    assert profile.disliked_tags == []


@pytest.mark.asyncio
async def test_generate_search_query(mock_llm_client, sample_tag_stats):
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
    profile = await learner.analyze_preferences(sample_tag_stats, tag_limit=2)
    query = await learner.generate_search_query(profile)

    assert query == ["tag1", "tag2"]
