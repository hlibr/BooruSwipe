"""API routes for BooruSwipe."""

import logging
import os
import asyncio
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
import httpx

logger = logging.getLogger(__name__)

def log_swipe(msg: str):
    logging.info(msg, extra={"category": "SWIPE"})

def log_llm(msg: str):
    logging.info(msg, extra={"category": "LLM"})

def log_llm_summary(msg: str):
    logging.info(msg, extra={"category": "LLM_SUMMARY"})

def log_image(msg: str):
    logging.info(msg, extra={"category": "IMAGE"})

def log_error(msg: str):
    logging.error(msg, extra={"category": "ERROR"})


def get_random_tag() -> str:
    """Get the correct random tag for the configured booru source.
    
    Returns:
        str: "sort:random" for Gelbooru, "random:1" for Danbooru
    """
    booru_source = os.getenv("BOORU_SOURCE", "danbooru").lower()
    if booru_source == "gelbooru":
        return "sort:random"
    else:
        return "random:1"

from booruswipe.db.repository import Repository
from booruswipe.gelbooru.client import DanbooruClient, GelbooruClient
from booruswipe.llm.preference_learner import PreferenceLearner
from booruswipe.db.models import PreferenceProfile as PreferenceProfileModel
from booruswipe.api.deps import (
    get_repository,
    get_booru_client,
    get_optional_preference_learner,
    check_booru_client,
    is_verbose_mode,
)
from fastapi import BackgroundTasks


router = APIRouter(prefix="/api")


llm_lock = asyncio.Lock()
llm_state = {"is_processing": False, "dirty": False}


class ImageResponse(BaseModel):
    """Response model for image endpoint."""
    id: int
    url: str
    tags: List[str]
    sample_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


@router.get("/image/{image_id}")
async def serve_image(
    image_id: int,
    repository: Repository = Depends(get_repository),
    booru_client: Union[DanbooruClient, GelbooruClient] = Depends(get_booru_client),
) -> Response:
    """Proxy image through backend to bypass Gelbooru hotlink protection.
    
    Fetches image directly from booru API with proper credentials and returns raw bytes.
    No database lookup required - works for images not yet saved.
    """
    # Fetch image data from booru API directly
    try:
        image_data = await booru_client.get_post(image_id)
        image_url = image_data.url
    except Exception as e:
        logger.error(f"Failed to fetch image {image_id} from booru: {e}")
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Fetch image bytes with credentials and proper headers
    async with httpx.AsyncClient() as client:
        # Set Referer to tell Gelbooru this is a legitimate post view
        headers = {
            "Referer": f"https://gelbooru.com/index.php?page=post&s=view&id={image_id}"
        }
        response = await client.get(image_url, headers=headers)
        
        # If we got HTML instead of image, try sample_url as fallback
        content_type = response.headers.get("content-type", "")
        if response.status_code != 200 or "image" not in content_type:
            # Try sample URL instead
            try:
                sample_url = image_data.sample_url
                if sample_url:
                    response = await client.get(sample_url, headers=headers)
            except:
                pass
        
        # Final check - if still not an image, return error
        content_type = response.headers.get("content-type", "")
        if response.status_code != 200 or "image" not in content_type:
            logger.error(f"Could not fetch image {image_id}: got {content_type}")
            raise HTTPException(status_code=502, detail="Could not fetch image")
    
    # Return raw image bytes
    return Response(
        response.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"}
    )


class SwipeRequest(BaseModel):
    """Request model for swipe endpoint."""
    image_id: int
    direction: str
    weight: int = 1
    
    class Config:
        json_schema_extra = {
            "example": {
                "image_id": 123456,
                "direction": "right",
                "weight": 1
            }
        }


class SwipeResponse(BaseModel):
    """Response model for swipe endpoint."""
    success: bool
    next_image: Optional[ImageResponse] = None


class LLMSettings(BaseModel):
    """Request model for LLM settings."""
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str  # Required, no default


class LLMTestRequest(BaseModel):
    """Request model for testing LLM connection."""
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str  # Required, no default
    prompt: str = "Hello"


class SessionState:
    """Session state for managing image queues."""
    
    def __init__(self):
        self.current_image: Optional[Dict[str, Any]] = None
        self.swipe_count = 0
        self.pending_swipes: List[Dict[str, Any]] = []


_session = SessionState()


@asynccontextmanager
async def session_context():
    """Context manager for session state."""
    yield _session


async def run_llm_analysis(repository, preference_learner):
    """Run LLM analysis with dirty flag state machine.
    
    Creates its own independent DB session to avoid transaction closed errors
    when running as a background task.
    """
    llm_state["is_processing"] = True
    LLM_MAX_TAGS = int(os.getenv("LLM_MAX_TAGS", "100"))
    LLM_TAG_FILTER_MIN_COUNT = int(os.getenv("LLM_TAG_FILTER_MIN_COUNT", "1"))
    BOORU_TAGS_PER_SEARCH = int(os.getenv("BOORU_TAGS_PER_SEARCH", "2"))
    
    async with repository.async_sessionmaker() as session:
        try:
            tag_freqs = await repository.get_tag_counts_for_llm(session, limit=LLM_MAX_TAGS, min_absolute_count=LLM_TAG_FILTER_MIN_COUNT)
            tag_counts_formatted = {
                tag: data["net_count"]
                for tag, data in tag_freqs.items()
            }
            
            recent_scores = await repository.get_recent_tag_scores(limit=20)
            
            learned_profile = await preference_learner.analyze_preferences(tag_counts_formatted, tag_limit=BOORU_TAGS_PER_SEARCH, recent_tag_scores=recent_scores)
            
            db_profile = await repository.get_or_create_profile(session)
            db_profile.preferences = learned_profile.to_dict()
            await repository.save_profile(session, db_profile)
            
            log_llm(f"CUMULATIVE TAGS (all-time): {', '.join(f'{tag} ({data})' for tag, data in list(tag_counts_formatted.items())[:10])}")
            log_llm(f"RECENT TAGS (top 10): {', '.join(f'{tag} ({score:+d})' for tag, score in list(recent_scores.items())[:10]) if recent_scores else 'No recent data'}")
            log_llm(f"Analyzed preferences with tag frequencies: {tag_counts_formatted}")
            if db_profile.preferences.get('liked_tags'):
                log_llm(f"Response: liked_tags={db_profile.preferences.get('liked_tags', [])}")
            if db_profile.preferences.get('disliked_tags'):
                log_llm(f"Response: disliked_tags={db_profile.preferences.get('disliked_tags', [])}")
            log_llm(f"Response: recommended_search_tags={db_profile.preferences.get('recommended_search_tags', [])}")
            log_llm_summary(f"preferences_summary='{db_profile.preferences.get('preferences_summary', '')}'")
            log_llm(f"Profile saved to database")
        except Exception as e:
            log_llm(f"LLM analysis failed: {type(e).__name__}: {str(e)}")
            import traceback
            log_llm(f"Traceback: {traceback.format_exc()}")
        finally:
            llm_state["is_processing"] = False
            
            if llm_state["dirty"]:
                llm_state["dirty"] = False
                log_llm("Analysis complete: dirty=True, re-trigger=True")
                await maybe_trigger_llm(repository, preference_learner)
            else:
                log_llm("Analysis complete: dirty=False, re-trigger=False")


async def maybe_trigger_llm(repository, preference_learner):
    """Trigger LLM analysis based on dirty flag logic."""
    LLM_MIN_SWIPES = int(os.getenv("LLM_MIN_SWIPES", "5"))
    if _session.swipe_count < LLM_MIN_SWIPES:
        log_llm(f"Skipping LLM analysis: {_session.swipe_count} swipes < {LLM_MIN_SWIPES} threshold")
        return
    
    async with llm_lock:
        if llm_state["is_processing"]:
            llm_state["dirty"] = True
            log_llm("Triggered: queued for re-run (dirty=True, already processing)")
        else:
            log_llm(f"Triggered: running now (swipe_count={_session.swipe_count}, dirty=False)")
            await run_llm_analysis(repository, preference_learner)


def _build_image_response(image: Any, booru_source: str) -> ImageResponse:
    """Build image response with correct URL (proxy for Gelbooru)."""
    if booru_source == "gelbooru":
        url = f"/api/image/{image.id}"  # Proxy URL
    else:
        url = image.url  # Direct URL for Danbooru
    
    return ImageResponse(
        id=image.id,
        url=url,
        tags=image.tags,
        sample_url=image.sample_url if image.sample else None,
        width=image.width,
        height=image.height,
    )


async def select_next_image(
    repository: Repository,
    booru_client: Union[DanbooruClient, GelbooruClient],
    preference_learner: Optional[PreferenceLearner],
    seen_ids: set[int],
    swipe_count: int,
) -> Any:
    """Select next image using full 3-level fallback with delays.
    
    Hierarchy:
    1. Below LLM_MIN_SWIPES → Truly random seed images (no tags)
    2. Above threshold → LLM recommendations with progressive fallback
    3. Fallback → Tag frequencies (with 0.5s delays)
    4. Final → Random image (with 0.5s delays)
    
    Returns:
        Image object with id, url, tags, sample, width, height
    """
    BOORU_TAGS_PER_SEARCH = int(os.getenv("BOORU_TAGS_PER_SEARCH", "2"))
    BOORU_TAGS_PER_SEARCH_FALLBACK = int(os.getenv("BOORU_TAGS_PER_SEARCH_FALLBACK", "2"))
    profile = await repository.get_or_create_profile()
    LLM_MIN_SWIPES = int(os.getenv("LLM_MIN_SWIPES", "5"))
    
    # Read env vars at runtime (after .env is loaded)
    RANDOM_IMAGE_CHANCE = int(os.getenv("RANDOM_IMAGE_CHANCE", "10"))
    
    # Check random chance FIRST (before any fallback logic)
    import random
    if RANDOM_IMAGE_CHANCE > 0 and random.randint(1, 100) <= RANDOM_IMAGE_CHANCE:
        log_image(f"Random image triggered ({RANDOM_IMAGE_CHANCE}% chance)")
        try:
            return await booru_client.get_random_image()
        except Exception as e:
            log_error(f"Random image failed: {type(e).__name__}: {e}, falling back to normal selection")
    
    image = None
    
    log_image("Selection started")
    
    try:
        log_image(f"Loaded {len(seen_ids)} seen image IDs for filtering")
        
        # Skip LLM and tag fallbacks when below threshold - use truly random seed images
        if swipe_count < LLM_MIN_SWIPES:
            log_image(f"Below LLM threshold ({swipe_count} < {LLM_MIN_SWIPES}) - selecting random seed image")
            # random_images = await booru_client.search_images([], limit=100)
            # filtered = [img for img in random_images if img.id not in seen_ids]
            # if filtered:
            #     import random
            #     image = random.choice(filtered)
            #     log_image(f"Selected random seed image {image.id}")


            random_tag = get_random_tag()
            images = await booru_client.search_images([random_tag], limit=50)
            log_image(f"Gelbooru returned {len(images)} images")
            filtered = [img for img in images if img.id not in seen_ids]
            if len(filtered) < len(images):
                log_image(f"Filtered out {len(images) - len(filtered)} already-seen images")
            if filtered:
                import random
                image = random.choice(filtered)
        
        # Level 1: LLM recommendations
        search_tags = profile.preferences.get("recommended_search_tags", [])
        if search_tags:
            llm_tags = search_tags[:BOORU_TAGS_PER_SEARCH]
            log_image(f"Level 1 - Using LLM recommendations: {', '.join(llm_tags)}")
            
            # Try with all tags first
            images = await booru_client.search_images(llm_tags, limit=50)
            log_image(f"Gelbooru returned {len(images)} images")
            
            filtered = [img for img in images if img.id not in seen_ids]
            if len(filtered) < len(images):
                log_image(f"Filtered out {len(images) - len(filtered)} already-seen images")
            if filtered:
                import random
                image = random.choice(filtered)
                log_image(f"Selected image {image.id}")
            elif len(llm_tags) > 1:
                # If no results, remove HALF the tags randomly and try once
                half_count = len(llm_tags) // 2
                remaining_tags = random.sample(llm_tags, half_count)
                log_image(f"No results - trying {half_count} random tags: {', '.join(remaining_tags)}")
                
                images = await booru_client.search_images(remaining_tags, limit=50)
                log_image(f"Gelbooru returned {len(images)} images")
                
                filtered = [img for img in images if img.id not in seen_ids]
                if len(filtered) < len(images):
                    log_image(f"Filtered out {len(images) - len(filtered)} already-seen images")
                if filtered:
                    image = random.choice(filtered)
                    log_image(f"Selected image {image.id}")
                else:
                    log_image("Level 1 failed - moving to Level 2")
            else:
                log_image("Level 1 failed - moving to Level 2")
        
        # Level 2: Fallback to raw tag frequencies (only if above LLM threshold)
        if image is None and swipe_count >= LLM_MIN_SWIPES:
            await asyncio.sleep(0.5)
            top_tags = await repository.get_top_liked_tags(limit=BOORU_TAGS_PER_SEARCH_FALLBACK)
            if top_tags:
                log_image(f"Level 2 - Using top liked tags: {', '.join(top_tags)}")
                images = await booru_client.search_images(top_tags, limit=50)
                log_image(f"Gelbooru returned {len(images)} images")
                filtered = [img for img in images if img.id not in seen_ids]
                if len(filtered) < len(images):
                    log_image(f"Filtered out {len(images) - len(filtered)} already-seen images")
                if filtered:
                    import random
                    image = random.choice(filtered)
                    log_image(f"Selected image {image.id} with tags: {', '.join(image.tags[:5])}")
        
        # Level 3: Final fallback to random (only if above LLM threshold)
        if image is None and swipe_count >= LLM_MIN_SWIPES:
            await asyncio.sleep(0.5)
            log_image("Level 3 - Using random image (no tags available)")
            random_tag = get_random_tag()
            if len(seen_ids) < 100:
                # Create individual -id:XXX tags for blacklist
                # blacklist_tags = [f'-id:{id}' for id in list(seen_ids)[:50]]
                tags = [random_tag]# + blacklist_tags
                images = await booru_client.search_images(tags, limit=10)
                log_image(f"Gelbooru returned {len(images)} images")
                if images:
                    import random
                    image = random.choice(images)
            else:
                images = await booru_client.search_images([random_tag], limit=50)
                log_image(f"Gelbooru returned {len(images)} images")
                filtered = [img for img in images if img.id not in seen_ids]
                if len(filtered) < len(images):
                    log_image(f"Filtered out {len(images) - len(filtered)} already-seen images")
                if filtered:
                    import random
                    image = random.choice(filtered)
            
            if image is None:
                image = await booru_client.get_random_image()
            log_image(f"Selected random image {image.id}")
        
        # Emergency fallback if still no image (below threshold and random returned nothing)
        if image is None:
            log_image("Emergency fallback: getting random image")
            image = await booru_client.get_random_image()
            
    except Exception as e:
        log_error(f"Failed to fetch image from booru: {e}")
        raise
    
    return image


@router.get("/image", response_model=ImageResponse)
async def get_image(
    repository: Repository = Depends(get_repository),
    booru_client: Union[DanbooruClient, GelbooruClient] = Depends(get_booru_client),
    preference_learner: Optional[PreferenceLearner] = Depends(get_optional_preference_learner),
) -> ImageResponse:
    """Get the next image to display.
    
    Uses a 3-level fallback hierarchy:
    1. LLM recommendations from profile (with progressive tag dropping)
    2. Fallback: Raw tag frequencies (top net-liked tags)
    3. Final fallback: Random from configured booru source
    """
    # Return already-selected image if exists (from /api/swipe)
    if _session.current_image is not None:
        log_image(f"Returning already-selected image {_session.current_image['id']}")
        return ImageResponse(**_session.current_image)
    
    check_booru_client(booru_client)
    
    DOUBLE_LIKED_NEVER_IGNORE = os.getenv("DOUBLE_LIKED_NEVER_IGNORE", "true").lower() == "true"
    
    try:
        seen_ids = await repository.get_filtered_swiped_image_ids(
            limit=1000,
            exclude_double_liked=DOUBLE_LIKED_NEVER_IGNORE
        )
        image = await select_next_image(repository, booru_client, preference_learner, seen_ids, _session.swipe_count)
    except Exception as e:
        log_error(f"Failed to fetch image from booru: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch image from booru: {str(e)}",
        )
    
    # Only proxy Gelbooru, direct-link Danbooru
    booru_source = os.getenv("BOORU_SOURCE", "danbooru").lower()
    response = _build_image_response(image, booru_source)
    
    _session.current_image = {
        "id": image.id,
        "url": response.url,
        "tags": image.tags,
        "sample_url": image.sample_url if image.sample else None,
        "width": image.width,
        "height": image.height,
    }
    
    return response


@router.post("/swipe", response_model=SwipeResponse)
async def record_swipe(
    swipe_request: SwipeRequest,
    background_tasks: BackgroundTasks,
    repository: Repository = Depends(get_repository),
    booru_client: Union[DanbooruClient, GelbooruClient] = Depends(get_booru_client),
    preference_learner: Optional[PreferenceLearner] = Depends(get_optional_preference_learner),
) -> SwipeResponse:
    """Record a swipe and get the next image.
    
    Args:
        swipe_request: Swipe data with image_id and direction ("left" or "right")
        
    Returns:
        Success status and optionally the next image
    """
    if swipe_request.direction not in ("left", "right"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direction must be 'left' or 'right'",
        )
    
    liked = swipe_request.direction == "right"
    
    if _session.current_image is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No current image to swipe on",
        )
    
    current = _session.current_image
    
    log_swipe(f"Received: direction={swipe_request.direction}, image_id={swipe_request.image_id}, tag_count={len(current['tags'])}")
    
    try:
        LLM_MIN_SWIPES = int(os.getenv("LLM_MIN_SWIPES", "5"))
        BOORU_TAGS_PER_SEARCH = int(os.getenv("BOORU_TAGS_PER_SEARCH", "2"))
        booru_source = os.getenv("BOORU_SOURCE", "danbooru").lower()
        await repository.save_swipe(
            booru=booru_source,
            image_id=str(swipe_request.image_id),
            post_url=current["url"],
            file_url=current["url"],
            tags=current["tags"],
            liked=liked,
        )
        
        await repository.add_swiped_image(swipe_request.image_id, liked)
        
        if swipe_request.weight >= 2 and liked:
            await repository.add_double_liked_image(swipe_request.image_id)
            log_swipe(f"Recorded double-liked image {swipe_request.image_id} (never ignore)")
        else:
            log_swipe(f"Recorded swiped image {swipe_request.image_id} (liked={liked})")
        
        for tag in current["tags"]:
            await repository.update_tag_count(tag, liked, weight=swipe_request.weight)
        log_swipe(f"Tag counts updated for {len(current['tags'])} tags (weight={swipe_request.weight})")
        
        _session.swipe_count += 1
        _session.pending_swipes.append({
            "image_id": swipe_request.image_id,
            "liked": liked,
            "tags": current["tags"],
        })
        
        if preference_learner:
            background_tasks.add_task(maybe_trigger_llm, repository, preference_learner)
            log_swipe("LLM trigger queued in background task")
        
        next_image = None
        try:
            check_booru_client(booru_client)
            DOUBLE_LIKED_NEVER_IGNORE = os.getenv("DOUBLE_LIKED_NEVER_IGNORE", "true").lower() == "true"
            seen_ids = await repository.get_filtered_swiped_image_ids(
                limit=1000,
                exclude_double_liked=DOUBLE_LIKED_NEVER_IGNORE
            )
            
            try:
                image = await select_next_image(repository, booru_client, preference_learner, seen_ids, _session.swipe_count)
                
                booru_source = os.getenv("BOORU_SOURCE", "danbooru").lower()
                next_image = _build_image_response(image, booru_source)
                
                _session.current_image = {
                    "id": image.id,
                    "url": next_image.url,
                    "tags": image.tags,
                    "sample_url": image.sample_url if image.sample else None,
                    "width": image.width,
                    "height": image.height,
                }
                log_image(f"Next image selected: id={image.id}")
            except Exception as e:
                booru_source = os.getenv("BOORU_SOURCE", "danbooru").lower()
                log_error(f"Failed to fetch next image from {booru_source.title()}: {type(e).__name__}: {e}")
                import traceback
                log_error(f"Traceback: {traceback.format_exc()}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to select next image: {str(e)}"
                )
        except HTTPException:
            raise
        except Exception as e:
            log_error(f"Swipe endpoint error: {type(e).__name__}: {e}")
            import traceback
            log_error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to record swipe: {str(e)}"
            )
        
        return SwipeResponse(success=True, next_image=next_image)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record swipe: {str(e)}",
        )


@router.get("/stats")
async def get_stats(
    repository: Repository = Depends(get_repository),
) -> Dict[str, Any]:
    """Get swipe statistics."""
    try:
        swipes = await repository.get_swipes(limit=1000)
        total = len(swipes)
        likes = sum(1 for s in swipes if s.liked)
        return {
            "total_swipes": total,
            "likes": likes,
            "dislikes": total - likes,
            "session_swipes": _session.swipe_count,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}",
        )


def _get_settings_path() -> Path:
    """Get the path to the settings file."""
    return Path(__file__).parent.parent.parent / "booru.conf"


def _load_llm_settings() -> Dict[str, str]:
    """Load LLM settings from .env file."""
    settings_path = _get_settings_path()
    settings = {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "",
    }
    if settings_path.exists():
        with open(settings_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip().lower()
                    if key in settings:
                        settings[key] = value.strip()
    return settings


def _save_llm_settings(settings: Dict[str, str]) -> None:
    """Save LLM settings to .env file."""
    settings_path = _get_settings_path()
    with open(settings_path, "w") as f:
        f.write(f"api_key={settings.get('api_key', '')}\n")
        f.write(f"base_url={settings.get('base_url', '')}\n")
        f.write(f"model={settings.get('model', '')}\n")


@router.get("/settings")
async def get_settings() -> Dict[str, str]:
    """Get current LLM settings."""
    return _load_llm_settings()


@router.post("/settings")
async def save_settings(settings: LLMSettings) -> Dict[str, Any]:
    """Save LLM settings to .env file."""
    try:
        settings_dict = {
            "api_key": settings.api_key,
            "base_url": settings.base_url,
            "model": settings.model,
        }
        _save_llm_settings(settings_dict)
        return {"success": True}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save settings: {str(e)}",
        )


@router.post("/settings/test")
async def test_settings(test_request: LLMTestRequest) -> Dict[str, Any]:
    """Test LLM connection with provided settings."""
    try:
        async with httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {test_request.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        ) as client:
            response = await client.post(
                f"{test_request.base_url.rstrip('/')}/chat/completions",
                json={
                    "messages": [{"role": "user", "content": test_request.prompt}],
                    "model": test_request.model,
                    "temperature": 0.7,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "success": True,
                "message": "Connection successful",
                "response": content[:100] if content else "",
            }
    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"HTTP error: {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"success": False, "error": f"Connection failed: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
