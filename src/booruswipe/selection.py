"""Helpers for choosing images from search results."""

from dataclasses import dataclass
from typing import Generic, Mapping, Optional, Sequence, TypeVar

T = TypeVar("T")

CUMULATIVE_TAG_WEIGHT = 1.0
RECENT_TAG_WEIGHT = 1.5
ANIMATED_TAGS = {
    "animated",
    "animated_gif",
    "animated_png",
    "looping_animation",
    "ugoira",
}
ANIMATED_MEDIA_TYPES = {
    "image/apng",
    "image/gif",
    "video/mp4",
    "video/webm",
}


@dataclass(frozen=True)
class ScoredImage(Generic[T]):
    """An image paired with its local ranking score."""

    image: T
    score: float


def decay_value(
    value: float,
    age_swipes: float,
    half_life_swipes: float,
) -> float:
    """Apply exponential decay to a score based on swipe distance.

    A half-life of 30 swipes means the value is cut in half every 30 swipes.
    Pass a non-positive half-life to disable decay.
    """
    if half_life_swipes <= 0:
        return float(value)

    decay_factor = 0.5 ** (max(0.0, age_swipes) / half_life_swipes)
    return float(value) * decay_factor


def compact_recent_tag_scores(
    recent_tag_scores: Mapping[str, float],
    limit: int,
    cumulative_liked_tags: Optional[set[str]] = None,
) -> dict[str, float]:
    """Keep the strongest recent tags by absolute score.

    Positive tags already present in the cumulative liked set can be filtered
    out before ranking. Zero-score tags are discarded because they do not carry
    directional signal.
    """
    if limit <= 0 or not recent_tag_scores:
        return {}

    scored_tags = []
    for tag, score in recent_tag_scores.items():
        if score == 0:
            continue
        if cumulative_liked_tags and score > 0 and tag in cumulative_liked_tags:
            continue
        scored_tags.append((tag, score))

    scored_tags.sort(key=lambda item: (-abs(item[1]), -item[1], item[0]))
    return dict(scored_tags[:limit])


def compact_recent_tag_scores_split(
    recent_tag_scores: Mapping[str, float],
    positive_limit: int,
    negative_limit: int,
    cumulative_liked_tags: Optional[set[str]] = None,
) -> dict[str, float]:
    """Keep the strongest recent positive and negative tags separately."""
    if (positive_limit <= 0 and negative_limit <= 0) or not recent_tag_scores:
        return {}

    positive_tags = []
    negative_tags = []
    for tag, score in recent_tag_scores.items():
        if score == 0:
            continue
        if cumulative_liked_tags and score > 0 and tag in cumulative_liked_tags:
            continue
        if score > 0:
            positive_tags.append((tag, score))
        else:
            negative_tags.append((tag, score))

    positive_tags.sort(key=lambda item: (-item[1], item[0]))
    negative_tags.sort(key=lambda item: (item[1], item[0]))
    return dict(positive_tags[:max(0, positive_limit)] + negative_tags[:max(0, negative_limit)])


def is_animated_image(image: object) -> bool:
    """Return True when the candidate is clearly animated."""
    media_type = str(getattr(image, "media_type", "") or "").lower()
    if media_type in ANIMATED_MEDIA_TYPES or media_type.startswith("video/"):
        return True

    url_candidates = [
        getattr(image, "sample_url", ""),
        getattr(image, "url", ""),
    ]
    for url in url_candidates:
        lower_url = str(url or "").lower()
        if lower_url.endswith((".gif", ".apng", ".mp4", ".webm")):
            return True

    tags = {str(tag).strip().lower() for tag in getattr(image, "tags", []) or [] if str(tag).strip()}
    return any(tag in tags for tag in ANIMATED_TAGS)


def pick_first_non_animated(images: Sequence[T]) -> Optional[T]:
    """Return the first image that is not animated."""
    for image in images:
        if not is_animated_image(image):
            return image
    return None


def filter_non_animated(images: Sequence[T]) -> list[T]:
    """Return only non-animated images from a sequence."""
    return [image for image in images if not is_animated_image(image)]


def pick_first_unseen(images: Sequence[T], seen_ids: set[int]) -> Optional[T]:
    """Return the first image whose id is not present in ``seen_ids``."""
    for image in images:
        if getattr(image, "id", None) not in seen_ids:
            return image
    return None


def score_image(
    image: object,
    cumulative_tag_scores: Mapping[str, float],
    recent_tag_scores: Mapping[str, float],
) -> float:
    """Score an image using cumulative and recent tag affinity."""
    total = 0.0
    tags = getattr(image, "tags", []) or []
    for tag in dict.fromkeys(str(tag) for tag in tags if tag):
        total += cumulative_tag_scores.get(tag, 0) * CUMULATIVE_TAG_WEIGHT
        total += recent_tag_scores.get(tag, 0) * RECENT_TAG_WEIGHT
    return total


def pick_best_scored_unseen(
    images: Sequence[T],
    seen_ids: set[int],
    cumulative_tag_scores: Mapping[str, float],
    recent_tag_scores: Mapping[str, float],
) -> Optional[ScoredImage[T]]:
    """Return the highest-scoring unseen image from a result set."""
    best: Optional[ScoredImage[T]] = None
    for image in images:
        if getattr(image, "id", None) in seen_ids:
            continue

        score = score_image(image, cumulative_tag_scores, recent_tag_scores)
        if best is None or score > best.score:
            best = ScoredImage(image=image, score=score)

    return best
