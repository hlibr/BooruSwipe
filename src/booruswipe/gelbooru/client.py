"""Async HTTP clients for Booru image boards."""
import logging
import os
from typing import List, Optional
from urllib.parse import urlencode

import httpx

from .models import Image, Tag

logger = logging.getLogger(__name__)

def log_image(msg: str):
    logging.info(msg, extra={"category": "IMAGE"})

def log_error(msg: str):
    logging.error(msg, extra={"category": "ERROR"})


class DanbooruClient:
    """Async client for Danbooru API."""
    
    BASE_URL = "https://danbooru.donmai.us/posts.json"
    
    def __init__(self, api_key: Optional[str] = None, user_id: Optional[str] = None):
        """Initialize the client.
        
        Args:
            api_key: Optional API key for higher rate limits
            user_id: Optional user ID for higher rate limits
        """
        self.api_key = api_key
        self.user_id = user_id
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> "DanbooruClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _request(self, **params) -> dict:
        """Make a request to the Danbooru API."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": "BooruSwipe/1.0"},
                follow_redirects=True
            )
        
        headers = {"User-Agent": "BooruSwipe/1.0"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        self._client.headers = headers
        
        url = f"{self.BASE_URL}?{urlencode(params)}"
        
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()
    
    async def get_random_image(self) -> Image:
        """Fetch a random image from Danbooru.
        
        Returns:
            Image: An Image object with url and tags.
        """
        log_image("Requesting random image from Danbooru")
        data = await self._request(tags="random:1", limit="1")
        
        if not data:
            raise ValueError("No images found")
        
        post = data[0] if isinstance(data, list) else data
        
        return Image.from_api(post)
    
    async def search_images(self, tags: List[str], limit: int = 100) -> List[Image]:
        """Search for images by tags.
        
        Args:
            tags: List of tags to search for.
            limit: Maximum number of images to return (max 100).
            
        Returns:
            List of Image objects matching the search criteria.
        """
        if limit > 100:
            limit = 100
        
        BOORU_TAGS_PER_SEARCH = int(os.getenv("BOORU_TAGS_PER_SEARCH", "2"))
        tags = tags[:BOORU_TAGS_PER_SEARCH]
        tag_string = " ".join(tags)
        log_image(f"Searching Danbooru for tags: {tag_string}")
        data = await self._request(tags=tag_string, limit=str(limit))
        
        if not data:
            log_image(f"No images found for tags: {tag_string}")
            return []
        
        if not isinstance(data, list):
            data = [data]
        
        log_image(f"Found {len(data)} images for tags: {tag_string}")
        return [Image.from_api(post) for post in data]
    
    async def get_post(self, post_id: int) -> Image:
        """Fetch a specific post by ID.
        
        Args:
            post_id: The post ID to fetch.
            
        Returns:
            Image object for the requested post.
        """
        log_image(f"Fetching post {post_id} from Danbooru")
        data = await self._request(tags=f"id:{post_id}", limit="1")
        
        if not data:
            raise ValueError(f"Post {post_id} not found")
        
        post = data[0] if isinstance(data, list) else data
        return Image.from_api(post)


class GelbooruClient:
    """Async client for Gelbooru API."""
    
    BASE_URL = "https://gelbooru.com/index.php"
    
    def __init__(self, api_key: Optional[str] = None, user_id: Optional[str] = None):
        """Initialize the Gelbooru client.
        
        Args:
            api_key: Optional API key for higher rate limits
            user_id: Optional user ID for higher rate limits
        """
        self.api_key = api_key
        self.user_id = user_id
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> "GelbooruClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _request(self, **params) -> dict:
        """Make a request to the Gelbooru API."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": "BooruSwipe/1.0"},
                follow_redirects=True
            )
        
        # Add authentication parameters
        if self.user_id:
            params["user_id"] = self.user_id
        if self.api_key:
            params["api_key"] = self.api_key
        
        params["page"] = "dapi"
        params["s"] = "post"
        params["q"] = "index"
        params["json"] = "1"
        
        url = f"{self.BASE_URL}?{urlencode(params)}"
        
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()
    
    async def get_random_image(self) -> Image:
        """Fetch a random image from Gelbooru.
        
        Returns:
            Image: An Image object with url and tags.
        """
        log_image("Requesting random image from Gelbooru")
        data = await self._request(tags="sort:random", limit=1)
        
        posts = data.get("post", []) if isinstance(data, dict) else data
        
        if not posts:
            raise ValueError("No images found")
        
        post = posts[0] if isinstance(posts, list) else posts
        
        return Image.from_api(post)
    
    async def search_images(self, tags: List[str], limit: int = 100) -> List[Image]:
        """Search for images by tags.
        
        Args:
            tags: List of tags to search for.
            limit: Maximum number of images to return (max 100).
            
        Returns:
            List of Image objects matching the search criteria.
        """
        if limit > 100:
            limit = 100
        
        BOORU_TAGS_PER_SEARCH = int(os.getenv("BOORU_TAGS_PER_SEARCH", "2"))
        tags = tags[:BOORU_TAGS_PER_SEARCH]
        tag_string = " ".join(tags)
        log_image(f"Searching Gelbooru for tags: {tag_string}")
        data = await self._request(tags=tag_string, limit=limit)
        
        posts = data.get("post", []) if isinstance(data, dict) else data
        
        if not posts:
            log_image(f"No images found for tags: {tag_string}")
            return []
        
        if not isinstance(posts, list):
            posts = [posts]
        
        log_image(f"Found {len(posts)} images for tags: {tag_string}")
        return [Image.from_api(post) for post in posts]
    
    async def get_post(self, post_id: int) -> Image:
        """Fetch a specific post by ID.
        
        Args:
            post_id: The post ID to fetch.
            
        Returns:
            Image object for the requested post.
        """
        log_image(f"Fetching post {post_id} from Gelbooru")
        data = await self._request(tags=f"id:{post_id}", limit=1)
        
        posts = data.get("post", []) if isinstance(data, dict) else data
        
        if not posts:
            raise ValueError(f"Post {post_id} not found")
        
        post = posts[0] if isinstance(posts, list) else posts
        return Image.from_api(post)
