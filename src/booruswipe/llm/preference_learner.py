"""Preference learning logic for LLM integration."""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from booruswipe.db.models import Swipe
from booruswipe.llm.client import LLMClient
from booruswipe.llm.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

def log_llm(msg: str):
    logging.info(msg, extra={"category": "LLM"})

def log_error(msg: str):
    logging.error(msg, extra={"category": "ERROR"})


# Load configuration from environment
# LLM_USE_STRUCTURED_OUTPUT: Enable strict JSON schema validation (default: True)
LLM_USE_STRUCTURED_OUTPUT = os.getenv("LLM_USE_STRUCTURED_OUTPUT", "true").lower() == "true"


class PreferenceProfile:
    """User preference profile withtags and statistics."""

    def __init__(
        self,
        liked_tags: list[str],
        disliked_tags: list[str],
        preferences_summary: str,
        recommended_search_tags: list[str],
        total_swipes: int = 0,
        total_likes: int = 0,
        total_dislikes: int = 0,
    ):
        """Initialize preference profile.

        Args:
            liked_tags: Tags user tends to like
            disliked_tags: Tags user tends to dislike
            preferences_summary: Natural language summary of preferences
            recommended_search_tags: Tags to use for search
            total_swipes: Total number of swipes
            total_likes: Total likes count
            total_dislikes: Total dislikes count
        """
        self.liked_tags = liked_tags
        self.disliked_tags = disliked_tags
        self.preferences_summary = preferences_summary
        self.recommended_search_tags = recommended_search_tags
        self.total_swipes = total_swipes
        self.total_likes = total_likes
        self.total_dislikes = total_dislikes

    def to_dict(self) -> dict[str, Any]:
        """Convert profile to dictionary for storage."""
        return {
            "liked_tags": self.liked_tags,
            "disliked_tags": self.disliked_tags,
            "preferences_summary": self.preferences_summary,
            "recommended_search_tags": self.recommended_search_tags,
            "total_swipes": self.total_swipes,
            "total_likes": self.total_likes,
            "total_dislikes": self.total_dislikes,
        }


class PreferenceLearner:
    """Learns user preferences from swipe history."""

    def __init__(self, client: LLMClient, verbose: bool = False):
        """Initialize preference learner.

        Args:
            client: LLMClient instance for API calls
            verbose: Whether to enable verbose logging
        """
        self.client = client
        self.verbose = verbose

    async def analyze_preferences(
        self,
        tag_stats: dict[str, dict[str, int]],
        tag_limit: int = 2,
        recent_tag_scores: Optional[dict[str, int]] = None,
    ) -> PreferenceProfile:
        """Analyze tag frequency data to extract user preferences.

        Args:
            tag_stats: Dictionary of tag -> liked_count, disliked_count, net_count
            tag_limit: Number of tags to recommend (BOORU_TAGS_PER_SEARCH)
            recent_tag_scores: Dictionary of tag -> net_score from last N swipes (optional)

        Returns:
            PreferenceProfile with extracted preferences
        """
        total_tags = len(tag_stats)
        
        if total_tags == 0:
            return PreferenceProfile(
                liked_tags=[],
                disliked_tags=[],
                preferences_summary="No tag frequency data available",
                recommended_search_tags=[],
                total_swipes=0,
                total_likes=0,
                total_dislikes=0,
            )

        positive_net_tags = {
            tag: data["net_count"] for tag, data in tag_stats.items() if data["net_count"] > 0
        }
        negative_net_tags = {
            tag: data["net_count"] for tag, data in tag_stats.items() if data["net_count"] < 0
        }

        sorted_positive_net = sorted(
            positive_net_tags.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        sorted_negative_net = sorted(
            negative_net_tags.items(),
            key=lambda item: item[1],
        )
        sorted_liked = sorted(
            tag_stats.items(),
            key=lambda item: (item[1]["liked_count"], item[1]["net_count"]),
            reverse=True,
        )
        sorted_disliked = sorted(
            tag_stats.items(),
            key=lambda item: (item[1]["disliked_count"], -item[1]["net_count"]),
            reverse=True,
        )

        top_10_positive_net = sorted_positive_net[:10]
        top_10_negative_net = sorted_negative_net[:10]

        liked_tags_str = ", ".join(
            f"{tag} ({data['liked_count']} likes, net {data['net_count']:+d})"
            for tag, data in sorted_liked[:20]
            if data["liked_count"] > 0
        )
        disliked_tags_str = ", ".join(
            f"{tag} ({data['disliked_count']} dislikes, net {data['net_count']:+d})"
            for tag, data in sorted_disliked[:20]
            if data["disliked_count"] > 0
        )

        log_llm(f"LLM Input: {total_tags} total unique tags")
        log_llm(
            f"LLM Input: Top 10 liked tags: "
            f"{[tag for tag, data in sorted_liked[:10] if data['liked_count'] > 0]}"
        )
        log_llm(
            f"LLM Input: Top 10 disliked tags: "
            f"{[tag for tag, data in sorted_disliked[:10] if data['disliked_count'] > 0]}"
        )


        # prompt = ""
        prompt = f"""
CUMULATIVE TAGS (all-time preference counts):
Top liked: {liked_tags_str if liked_tags_str else "No tags available"}
Top disliked: {disliked_tags_str if disliked_tags_str else "No tags available"}
"""

        if recent_tag_scores:
            sorted_recent = sorted(recent_tag_scores.items(), key=lambda x: x[1], reverse=True)
            recent_str = ", ".join(f"{tag} ({score:+d})" for tag, score in sorted_recent)
            prompt += f"""

RECENT TREND (likes/dislikes):
{recent_str if recent_str else "No recent data"}
"""

        prompt += f"""
Return JSON with:
- preferences_summary: brief natural language summary
- recommended_search_tags: EXACTLY {tag_limit} tags for the next image.
"""

        log_llm(f"Prompt: {prompt}")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        # Create dynamic schema with correct tag limit
        class PreferenceProfileResponse(BaseModel):
            preferences_summary: str
            recommended_search_tags: list[str] = Field(max_length=tag_limit)
            liked_tags: list[str] = []
            disliked_tags: list[str] = []

        response = None
        try:
            log_llm(
                f"Analysis started: {total_tags} tags "
                f"({len(top_10_positive_net)} net-positive, {len(top_10_negative_net)} net-negative)"
            )
            log_llm(
                f"Prompt: sending {sum(1 for _, data in sorted_liked[:20] if data['liked_count'] > 0)} liked tags, "
                f"{sum(1 for _, data in sorted_disliked[:20] if data['disliked_count'] > 0)} disliked tags"
            )

            response = await self.client.chat_completion(messages)
            content = response["choices"][0]["message"]["content"]

            # Strip markdown code blocks before parsing
            content = content.strip()
            if content.startswith("```"):
                # Remove opening ```json or ```
                content = content.split("```", 1)[1]
                if content.startswith("json"):
                    content = content[4:]
                # Remove closing ```
                content = content.rsplit("```", 1)[0]
                content = content.strip()

            # Remove any <think>...</think> sections if present
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


            parsed = json.loads(content)
            
            if LLM_USE_STRUCTURED_OUTPUT:
                # Use strict schema validation (enforces required fields and tag limits)
                validated = PreferenceProfileResponse.model_validate(parsed)
                liked_tags_len = len(validated.liked_tags)
                disliked_tags_len = len(validated.disliked_tags)
                recommendations_len = len(validated.recommended_search_tags)
                log_parts = [f"recommendations={recommendations_len}"]
                if liked_tags_len:
                    log_parts.insert(0, f"liked_tags={liked_tags_len}")
                if disliked_tags_len:
                    log_parts.insert(1, f"disliked_tags={disliked_tags_len}")
                log_llm(f"Response received: {', '.join(log_parts)}")
                return PreferenceProfile(
                    liked_tags=validated.liked_tags,
                    disliked_tags=validated.disliked_tags,
                    preferences_summary=validated.preferences_summary,
                    recommended_search_tags=validated.recommended_search_tags,
                    total_swipes=0,
                    total_likes=0,
                    total_dislikes=0,
                )
            else:
                # Lenient parsing: use existing behavior without schema validation
                liked_tags_len = len(parsed.get('liked_tags', []))
                disliked_tags_len = len(parsed.get('disliked_tags', []))
                recommendations_len = len(parsed.get('recommended_search_tags', []))
                log_parts = [f"recommendations={recommendations_len}"]
                if liked_tags_len:
                    log_parts.insert(0, f"liked_tags={liked_tags_len}")
                if disliked_tags_len:
                    log_parts.insert(1, f"disliked_tags={disliked_tags_len}")
                log_llm(f"Response received (lenient mode): {', '.join(log_parts)}")
                return PreferenceProfile(
                    liked_tags=parsed.get("liked_tags", []),
                    disliked_tags=parsed.get("disliked_tags", []),
                    preferences_summary=parsed.get("preferences_summary", ""),
                    recommended_search_tags=parsed.get("recommended_search_tags", []),
                    total_swipes=0,
                    total_likes=0,
                    total_dislikes=0,
                )
        except json.JSONDecodeError as e:
            log_error(f"Failed to parse LLM response as JSON: {e}")
            raw_content = response.get("choices", [{}])[0].get("message", {}).get("content", "N/A") if response else "N/A"
            log_error(f"Raw response: {raw_content[:200]}...")
            return PreferenceProfile(
                liked_tags=[],
                disliked_tags=[],
                preferences_summary="LLM analysis failed, using basic tag counts",
                recommended_search_tags=[],
                total_swipes=0,
                total_likes=0,
                total_dislikes=0,
            )
        except ValidationError as e:
            # Only raised when LLM_USE_STRUCTURED_OUTPUT=True
            log_error(f"Schema validation failed: {e}")
            raw_content = response.get("choices", [{}])[0].get("message", {}).get("content", "N/A") if response else "N/A"
            log_error(f"Raw response: {raw_content[:200]}...")
            return PreferenceProfile(
                liked_tags=[],
                disliked_tags=[],
                preferences_summary="LLM response validation failed, using basic tag counts",
                recommended_search_tags=[],
                total_swipes=0,
                total_likes=0,
                total_dislikes=0,
            )
        except Exception as e:
            log_error(f"LLM analysis FAILED: {type(e).__name__}: {e}")
            return PreferenceProfile(
                liked_tags=[],
                disliked_tags=[],
                preferences_summary="LLM analysis failed, using basic tag counts",
                recommended_search_tags=[],
                total_swipes=0,
                total_likes=0,
                total_dislikes=0,
            )

    async def generate_search_query(self, profile: PreferenceProfile) -> list[str]:
        """Generate search query tags based on preference profile.

        Args:
            profile: User's preference profile

        Returns:
            List of tags to use for searching
        """
        return profile.recommended_search_tags

    async def update_profile_from_swipe(
        self, profile: PreferenceProfile, swipe: Swipe
    ) -> PreferenceProfile:
        """Update profile with a new swipe.

        Args:
            profile: Current preference profile
            swipe: New swipe to incorporate

        Returns:
            Updated PreferenceProfile
        """
        total_swipes = profile.total_swipes + 1
        total_likes = profile.total_likes + (1 if swipe.liked else 0)
        total_dislikes = profile.total_dislikes + (1 if not swipe.liked else 0)

        new_profile = PreferenceProfile(
            liked_tags=profile.liked_tags,
            disliked_tags=profile.disliked_tags,
            preferences_summary=profile.preferences_summary,
            recommended_search_tags=profile.recommended_search_tags,
            total_swipes=total_swipes,
            total_likes=total_likes,
            total_dislikes=total_dislikes,
        )

        return new_profile
