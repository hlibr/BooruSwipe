"""Data models for booru API responses."""

from dataclasses import dataclass
from typing import Any, List
from urllib.parse import urlparse


@dataclass
class Image:
    """Represents an image from a booru API."""
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

    @staticmethod
    def _nested_get(data: dict[str, Any], *path: str) -> Any:
        """Walk a nested dictionary path and return the found value."""
        current: Any = data
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
            if current is None:
                return None
        return current

    @staticmethod
    def _flatten_tags(tags_data: Any) -> List[str]:
        """Normalize tag data from booru APIs into a flat list of strings."""
        if tags_data is None:
            return []
        if isinstance(tags_data, str):
            return [tag for tag in tags_data.split() if tag]
        if isinstance(tags_data, dict):
            flattened: List[str] = []
            for value in tags_data.values():
                flattened.extend(Image._flatten_tags(value))
            return flattened
        if isinstance(tags_data, list):
            flattened = []
            for tag in tags_data:
                if isinstance(tag, dict):
                    name = tag.get("name")
                    if name:
                        flattened.append(str(name))
                    else:
                        flattened.extend(Image._flatten_tags(list(tag.values())))
                else:
                    text = str(tag).strip()
                    if text:
                        flattened.append(text)
            return flattened

        text = str(tags_data).strip()
        return [text] if text else []
    
    @classmethod
    def from_api(cls, data: dict) -> "Image":
        """Create Image from API response data."""
        tags = cls._flatten_tags(data.get("tag_string") or data.get("tags", ""))

        file_url = data.get("file_url") or cls._nested_get(data, "file", "url") or ""
        large_file_url = data.get("large_file_url") or cls._nested_get(data, "large_file", "url") or ""
        sample_url = data.get("sample_url") or cls._nested_get(data, "sample", "url") or ""
        file_ext = data.get("file_ext") or cls._nested_get(data, "file", "ext") or ""
        width = data.get("image_width")
        if width is None:
            width = cls._nested_get(data, "file", "width")
        height = data.get("image_height")
        if height is None:
            height = cls._nested_get(data, "file", "height")

        return cls(
            url=file_url or "",
            tags=tags,
            id=int(data["id"]),
            width=int(width or 0),
            height=int(height or 0),
            sample=bool(
                data.get("has_large", False)
                or cls._nested_get(data, "sample", "has")
                or sample_url
                or large_file_url
            ),
            sample_url=sample_url or large_file_url or "",
            media_type=cls._guess_media_type(file_url or sample_url or large_file_url or "", file_ext),
            directory="",
        )


@dataclass
class Tag:
    """Represents a tag from a booru API."""
    name: str
    count: int
    type: int
