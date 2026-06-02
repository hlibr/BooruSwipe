"""Helpers for parsing and normalizing tag input."""

from typing import List, Optional


def parse_tag_field(value: Optional[str]) -> List[str]:
    """Parse a comma-separated tag field into normalized tag names."""
    if not value:
        return []

    tags: List[str] = []
    seen = set()
    for raw_tag in value.split(","):
        tag = raw_tag.strip().lstrip("-").strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)

    return tags
