"""Data models for Danbooru API responses."""

from dataclasses import dataclass
from typing import List


@dataclass
class Image:
    """Represents an image from Danbooru."""
    url: str
    tags: List[str]
    id: int
    width: int
    height: int
    sample: bool
    sample_url: str
    directory: str
    
    @classmethod
    def from_api(cls, data: dict) -> "Image":
        """Create Image from API response data."""
        tags_data = data.get("tag_string", data.get("tags", ""))
        if isinstance(tags_data, str):
            tags = tags_data.split()
        elif isinstance(tags_data, dict):
            tags = list(tags_data.values())
        elif isinstance(tags_data, list):
            tags = [tag["name"] if isinstance(tag, dict) else str(tag) for tag in tags_data]
        else:
            tags = []
        
        file_url = data.get("file_url")
        large_file_url = data.get("large_file_url")
        preview_file_url = data.get("preview_file_url")
        
        # Use preview or large for sample_url (lower resolution thumbnails)
        sample_url = preview_file_url or large_file_url or ""
        
        # ALWAYS use file_url (original/high-res) only - no fallback to lower resolution
        return cls(
            url=file_url or "",
            tags=tags,
            id=int(data["id"]),
            width=int(data.get("image_width", 0) or 0),
            height=int(data.get("image_height", 0) or 0),
            sample=bool(data.get("has_large", False)),
            sample_url=sample_url,
            directory=""
        )


@dataclass
class Tag:
    """Represents a tag from Danbooru."""
    name: str
    count: int
    type: int
