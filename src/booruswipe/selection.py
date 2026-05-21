"""Helpers for choosing images from sorted search results."""

from typing import Optional, Sequence, TypeVar

T = TypeVar("T")


def pick_first_unseen(images: Sequence[T], seen_ids: set[int]) -> Optional[T]:
    """Return the first image whose id is not present in ``seen_ids``."""
    for image in images:
        if getattr(image, "id", None) not in seen_ids:
            return image
    return None
