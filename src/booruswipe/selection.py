"""Helpers for choosing images from search results."""

from dataclasses import dataclass
from typing import Generic, Mapping, Optional, Sequence, TypeVar

T = TypeVar("T")

CUMULATIVE_TAG_WEIGHT = 1.0
RECENT_TAG_WEIGHT = 1.5


@dataclass(frozen=True)
class ScoredImage(Generic[T]):
    """An image paired with its local ranking score."""

    image: T
    score: float


def pick_first_unseen(images: Sequence[T], seen_ids: set[int]) -> Optional[T]:
    """Return the first image whose id is not present in ``seen_ids``."""
    for image in images:
        if getattr(image, "id", None) not in seen_ids:
            return image
    return None


def score_image(
    image: object,
    cumulative_tag_scores: Mapping[str, int],
    recent_tag_scores: Mapping[str, int],
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
    cumulative_tag_scores: Mapping[str, int],
    recent_tag_scores: Mapping[str, int],
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
