"""Data models for Danbooru API responses."""

from dataclasses import dataclass
from typing import List
from urllib.parse import urlparse


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
    media_type: str
    directory: str

    @staticmethod
    def _guess_media_type(url: str, file_ext: str = "") -> str:
        """Infer media type from API metadata or URL."""
        normalized_ext = (file_ext or "").lower().lstrip(".")
        if not normalized_ext and url:
            path = urlparse(url).path.lower()
            if "." in path:
                normalized_ext = path.rsplit(".", 1)[-1]

        if normalized_ext == "mp4":
            return "video/mp4"
        if normalized_ext == "webm":
            return "video/webm"
        return "image"
    
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
        sample_url = data.get("sample_url")
        file_ext = data.get("file_ext", "")
        
        # Gelbooru display should use only the explicit sample URL, or fall back to the original file.
        sample_url = sample_url or large_file_url or ""
        
        # ALWAYS use file_url (original/high-res) only - no fallback to lower resolution
        return cls(
            url=file_url or "",
            tags=tags,
            id=int(data["id"]),
            width=int(data.get("image_width", 0) or 0),
            height=int(data.get("image_height", 0) or 0),
            sample=bool(data.get("has_large", False)),
            sample_url=sample_url,
            media_type=cls._guess_media_type(file_url or sample_url or "", file_ext),
            directory=""
        )


@dataclass
class Tag:
    """Represents a tag from Danbooru."""
    name: str
    count: int
    type: int
