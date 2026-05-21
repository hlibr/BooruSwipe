"""Tests for booru API response normalization."""

from booruswipe.gelbooru.models import Image


def test_image_from_api_handles_flat_danbooru_payload():
    """Flat Danbooru-style payloads should still parse correctly."""
    image = Image.from_api(
        {
            "id": 123,
            "tag_string": "cat smile artist_tag",
            "file_url": "https://img.example.com/123.jpg",
            "sample_url": "https://img.example.com/sample/123.jpg",
            "file_ext": "jpg",
            "image_width": 1920,
            "image_height": 1080,
            "has_large": True,
        }
    )

    assert image.id == 123
    assert image.tags == ["cat", "smile", "artist_tag"]
    assert image.url == "https://img.example.com/123.jpg"
    assert image.sample_url == "https://img.example.com/sample/123.jpg"
    assert image.width == 1920
    assert image.height == 1080
    assert image.sample is True
    assert image.media_type == "image"


def test_image_from_api_handles_nested_e621_payload():
    """Nested e621-style payloads should be flattened into the shared image model."""
    image = Image.from_api(
        {
            "id": 456,
            "tags": {
                "general": ["cat", "smile"],
                "artist": ["artist_tag"],
                "species": ["feline"],
                "meta": ["highres"],
            },
            "file": {
                "url": "https://static1.e621.net/data/12/34/456.jpg",
                "width": 1600,
                "height": 900,
                "ext": "jpg",
            },
            "sample": {
                "url": "https://static1.e621.net/data/sample/456.jpg",
                "has": True,
            },
        }
    )

    assert image.id == 456
    assert image.tags == ["cat", "smile", "artist_tag", "feline", "highres"]
    assert image.url == "https://static1.e621.net/data/12/34/456.jpg"
    assert image.sample_url == "https://static1.e621.net/data/sample/456.jpg"
    assert image.width == 1600
    assert image.height == 900
    assert image.sample is True
    assert image.media_type == "image"
