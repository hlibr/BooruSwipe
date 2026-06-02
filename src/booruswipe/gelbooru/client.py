"""Async HTTP clients for Booru image boards."""
import asyncio
import logging
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional
from urllib.parse import urlencode

import httpx

from booruswipe.booru_sources import (
    get_animated_exclusion_tag,
    get_search_sort_mode,
    get_search_sort_tag,
    get_skip_animated_images,
)
from .models import Image
from booruswipe.selection import pick_first_non_animated

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

def log_image(msg: str):
    logging.info(msg, extra={"category": "IMAGE"})

def log_error(msg: str):
    logging.error(msg, extra={"category": "ERROR"})


def _normalize_fixed_tags(tags: Optional[List[str]]) -> List[str]:
    """Normalize fixed tags that should bypass the per-search cap."""
    normalized: List[str] = []
    seen = set()

    for tag in tags or []:
        clean_tag = tag.strip().lstrip("-").strip()
        if not clean_tag or clean_tag in seen:
            continue
        seen.add(clean_tag)
        normalized.append(clean_tag)

    return normalized


def _build_search_query_tags(
    tags: List[str],
    *,
    source_name: str,
    sort_mode: Optional[str],
    always_include_tags: Optional[List[str]] = None,
    always_include_negative_tags: Optional[List[str]] = None,
) -> tuple[List[str], str]:
    """Build a search tag list while keeping fixed tags outside the tag cap."""
    BOORU_TAGS_PER_SEARCH = int(os.getenv("BOORU_TAGS_PER_SEARCH", "6"))
    query_tags: List[str] = []
    seen = set()

    def add(tag: str) -> None:
        if tag and tag not in seen:
            seen.add(tag)
            query_tags.append(tag)

    for tag in _normalize_fixed_tags(always_include_tags):
        add(tag)

    for tag in tags[:BOORU_TAGS_PER_SEARCH]:
        add(tag)

    for tag in _normalize_fixed_tags(always_include_negative_tags):
        add(f"-{tag}")

    animated_exclusion_tag = get_animated_exclusion_tag()
    if animated_exclusion_tag:
        add(animated_exclusion_tag)

    effective_sort_mode = (sort_mode or get_search_sort_mode()).lower()
    if effective_sort_mode not in {"score", "random", "none"}:
        raise ValueError(f"Unsupported search sort mode: {effective_sort_mode}")
    if effective_sort_mode != "none":
        add(get_search_sort_tag(source_name, effective_sort_mode))

    return query_tags, effective_sort_mode


def _get_api_retry_settings() -> tuple[int, float, float]:
    """Read booru API retry settings from the environment."""
    return (
        max(1, int(os.getenv("BOORU_API_MAX_RETRIES", "3"))),
        max(0.0, float(os.getenv("BOORU_API_RETRY_BASE_DELAY", "0.5"))),
        max(0.0, float(os.getenv("BOORU_API_RETRY_MAX_DELAY", "8"))),
    )


def _parse_retry_after_seconds(retry_after: Optional[str]) -> Optional[float]:
    """Parse Retry-After header values into seconds."""
    if not retry_after:
        return None

    try:
        return max(0.0, float(retry_after))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(retry_after)
    except (TypeError, ValueError, IndexError):
        return None

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


async def _request_json_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    source_name: str,
    max_retries: int,
    base_delay: float,
    max_delay: float,
) -> dict:
    """GET JSON with retry/backoff for transient HTTP and network failures."""
    for attempt in range(max_retries):
        try:
            response = await client.get(url)

            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt == max_retries - 1:
                    log_error(
                        f"{source_name} API returned {response.status_code} on final attempt; giving up"
                    )
                    response.raise_for_status()

                retry_after = _parse_retry_after_seconds(response.headers.get("Retry-After"))
                wait_time = retry_after if retry_after is not None else min(
                    max_delay,
                    base_delay * (2 ** attempt),
                )
                log_error(
                    f"{source_name} API returned {response.status_code}; retrying in {wait_time:.2f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait_time)
                continue

            response.raise_for_status()
            return response.json()
        except httpx.RequestError as exc:
            if attempt == max_retries - 1:
                log_error(
                    f"{source_name} request failed after {max_retries} attempts: "
                    f"{type(exc).__name__}: {exc}"
                )
                raise

            wait_time = min(max_delay, base_delay * (2 ** attempt))
            log_error(
                f"{source_name} request failed with {type(exc).__name__}: {exc}; "
                f"retrying in {wait_time:.2f}s (attempt {attempt + 1}/{max_retries})"
            )
            await asyncio.sleep(wait_time)


class DanbooruClient:
    """Async client for Danbooru API."""
    
    BASE_URL = "https://danbooru.donmai.us/posts.json"
    POST_URL = "https://danbooru.donmai.us/posts/{post_id}.json"
    
    def __init__(self, api_key: Optional[str] = None, user_id: Optional[str] = None):
        """Initialize the client.
        
        Args:
            api_key: Optional API key for higher rate limits
            user_id: Optional Danbooru login name for authenticated requests
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
        
        self._client.headers = {"User-Agent": "BooruSwipe/1.0"}
        self._client.auth = (
            httpx.BasicAuth(self.user_id, self.api_key)
            if self.user_id and self.api_key
            else None
        )
        
        url = f"{self.BASE_URL}?{urlencode(params)}"
        max_retries, base_delay, max_delay = _get_api_retry_settings()
        return await _request_json_with_retries(
            self._client,
            url,
            source_name="Danbooru",
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
        )
    
    async def get_random_image(
        self,
        always_include_tags: Optional[List[str]] = None,
        always_include_negative_tags: Optional[List[str]] = None,
    ) -> Image:
        """Fetch a random image from Danbooru.
        
        Returns:
            Image: An Image object with url and tags.
        """
        log_image("Requesting random image from Danbooru")
        skip_animated = get_skip_animated_images()
        limit = 10 if skip_animated else 1
        attempts = 5 if skip_animated else 1

        for attempt in range(attempts):
            images = await self.search_images(
                ["random:1"],
                limit=limit,
                page=0,
                sort_mode="none",
                always_include_tags=always_include_tags,
                always_include_negative_tags=always_include_negative_tags,
            )

            if not images:
                continue

            image = (
                pick_first_non_animated(images)
                if skip_animated
                else images[0]
            )
            if image is not None:
                return image

            log_image(f"Skipping animated random image from Danbooru (attempt {attempt + 1}/{attempts})")

        raise ValueError("No non-animated images found")
    
    async def search_images(
        self,
        tags: List[str],
        limit: int = 100,
        page: int = 0,
        sort_mode: Optional[str] = None,
        always_include_tags: Optional[List[str]] = None,
        always_include_negative_tags: Optional[List[str]] = None,
    ) -> List[Image]:
        """Search for images by tags.

        Args:
            tags: List of tags to search for.
            limit: Maximum number of images to return (max 100).
            page: Page number (0-indexed) for pagination.
            sort_mode: Search sort mode ("score", "random", or "none").

        Returns:
            List of Image objects matching the search criteria.
        """
        if limit > 100:
            limit = 100

        query_tags, effective_sort_mode = _build_search_query_tags(
            tags,
            source_name="danbooru",
            sort_mode=sort_mode,
            always_include_tags=always_include_tags,
            always_include_negative_tags=always_include_negative_tags,
        )
        tag_string = " ".join(query_tags)
        log_image(
            f"Searching Danbooru for tags: {tag_string} "
            f"(sort_mode={effective_sort_mode}, page={page}, limit={limit})"
        )
        data = await self._request(tags=tag_string, limit=str(limit), page=str(page))

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
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": "BooruSwipe/1.0"},
                follow_redirects=True
            )

        self._client.headers = {"User-Agent": "BooruSwipe/1.0"}
        self._client.auth = (
            httpx.BasicAuth(self.user_id, self.api_key)
            if self.user_id and self.api_key
            else None
        )

        max_retries, base_delay, max_delay = _get_api_retry_settings()
        data = await _request_json_with_retries(
            self._client,
            self.POST_URL.format(post_id=post_id),
            source_name="Danbooru",
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
        )
        
        if not data:
            raise ValueError(f"Post {post_id} not found")
        
        return Image.from_api(data)


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
        max_retries, base_delay, max_delay = _get_api_retry_settings()
        return await _request_json_with_retries(
            self._client,
            url,
            source_name="Gelbooru",
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
        )
    
    async def get_random_image(
        self,
        always_include_tags: Optional[List[str]] = None,
        always_include_negative_tags: Optional[List[str]] = None,
    ) -> Image:
        """Fetch a random image from Gelbooru.
        
        Returns:
            Image: An Image object with url and tags.
        """
        log_image("Requesting random image from Gelbooru")
        skip_animated = get_skip_animated_images()
        limit = 10 if skip_animated else 1
        attempts = 5 if skip_animated else 1

        for attempt in range(attempts):
            images = await self.search_images(
                ["sort:random"],
                limit=limit,
                page=0,
                sort_mode="none",
                always_include_tags=always_include_tags,
                always_include_negative_tags=always_include_negative_tags,
            )

            if not images:
                continue

            image = (
                pick_first_non_animated(images)
                if skip_animated
                else images[0]
            )
            if image is not None:
                return image

            log_image(f"Skipping animated random image from Gelbooru (attempt {attempt + 1}/{attempts})")

        raise ValueError("No non-animated images found")
    
    async def search_images(
        self,
        tags: List[str],
        limit: int = 100,
        page: int = 0,
        sort_mode: Optional[str] = None,
        always_include_tags: Optional[List[str]] = None,
        always_include_negative_tags: Optional[List[str]] = None,
    ) -> List[Image]:
        """Search for images by tags.

        Args:
            tags: List of tags to search for.
            limit: Maximum number of images to return (max 100).
            page: Page number (0-indexed) for pagination.
            sort_mode: Search sort mode ("score", "random", or "none").

        Returns:
            List of Image objects matching the search criteria.
        """
        if limit > 100:
            limit = 100

        query_tags, effective_sort_mode = _build_search_query_tags(
            tags,
            source_name="gelbooru",
            sort_mode=sort_mode,
            always_include_tags=always_include_tags,
            always_include_negative_tags=always_include_negative_tags,
        )
        tag_string = " ".join(query_tags)
        log_image(
            f"Searching Gelbooru for tags: {tag_string} "
            f"(sort_mode={effective_sort_mode}, page={page}, limit={limit})"
        )
        data = await self._request(tags=tag_string, limit=limit, pid=page)

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


class E621Client:
    """Async client for e621 API."""

    BASE_URL = "https://e621.net/posts.json"

    def __init__(self, api_key: Optional[str] = None, user_id: Optional[str] = None):
        """Initialize the e621 client.

        Args:
            api_key: Optional API key for higher rate limits
            user_id: Optional e621 username for authenticated requests
        """
        self.api_key = api_key
        self.user_id = user_id
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "E621Client":
        """Async context manager entry."""
        self._client = httpx.AsyncClient()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(self, **params) -> dict:
        """Make a request to the e621 API."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": "BooruSwipe/1.0"},
                follow_redirects=True,
            )

        self._client.headers = {"User-Agent": "BooruSwipe/1.0"}
        self._client.auth = (
            httpx.BasicAuth(self.user_id, self.api_key)
            if self.user_id and self.api_key
            else None
        )

        url = f"{self.BASE_URL}?{urlencode(params)}"
        max_retries, base_delay, max_delay = _get_api_retry_settings()
        return await _request_json_with_retries(
            self._client,
            url,
            source_name="e621",
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
        )

    @staticmethod
    def _extract_posts(data: object) -> List[dict]:
        """Normalize e621 responses into a list of post dictionaries."""
        if isinstance(data, dict):
            posts = data.get("posts", data.get("post", []))
            if isinstance(posts, list):
                return posts
            if isinstance(posts, dict):
                return [posts]
            return []
        if isinstance(data, list):
            return data
        return []

    async def get_random_image(
        self,
        always_include_tags: Optional[List[str]] = None,
        always_include_negative_tags: Optional[List[str]] = None,
    ) -> Image:
        """Fetch a random image from e621."""
        log_image("Requesting random image from e621")

        last_error: Optional[Exception] = None
        skip_animated = get_skip_animated_images()
        limit = 10 if skip_animated else 1
        for random_tag in ("order:random", "random:1"):
            try:
                images = await self.search_images(
                    [random_tag],
                    limit=limit,
                    page=0,
                    sort_mode="none",
                    always_include_tags=always_include_tags,
                    always_include_negative_tags=always_include_negative_tags,
                )
            except Exception as exc:
                last_error = exc
                continue

            image = pick_first_non_animated(images) if skip_animated else (images[0] if images else None)
            if image is not None:
                return image

        if last_error is not None:
            raise last_error
        raise ValueError("No images found")

    async def search_images(
        self,
        tags: List[str],
        limit: int = 100,
        page: int = 0,
        sort_mode: Optional[str] = None,
        always_include_tags: Optional[List[str]] = None,
        always_include_negative_tags: Optional[List[str]] = None,
    ) -> List[Image]:
        """Search for images by tags."""
        if limit > 320:
            limit = 320

        query_tags, effective_sort_mode = _build_search_query_tags(
            tags,
            source_name="e621",
            sort_mode=sort_mode,
            always_include_tags=always_include_tags,
            always_include_negative_tags=always_include_negative_tags,
        )
        tag_string = " ".join(query_tags)
        api_page = page + 1
        log_image(
            f"Searching e621 for tags: {tag_string} "
            f"(sort_mode={effective_sort_mode}, page={page}, limit={limit})"
        )
        data = await self._request(tags=tag_string, limit=str(limit), page=str(api_page))

        posts = self._extract_posts(data)

        if not posts:
            log_image(f"No images found for tags: {tag_string}")
            return []

        log_image(f"Found {len(posts)} images for tags: {tag_string}")
        return [Image.from_api(post) for post in posts]

    async def get_post(self, post_id: int) -> Image:
        """Fetch a specific post by ID."""
        log_image(f"Fetching post {post_id} from e621")
        images = await self.search_images([f"id:{post_id}"], limit=1, page=0)

        if not images:
            raise ValueError(f"Post {post_id} not found")

        return images[0]


BooruClient = DanbooruClient | GelbooruClient | E621Client
