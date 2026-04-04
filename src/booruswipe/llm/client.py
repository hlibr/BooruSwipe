"""Client for OpenAI-compatible API endpoints."""

import logging
from typing import Any
import httpx
import asyncio

logger = logging.getLogger(__name__)

def log_llm(msg: str):
    logging.info(msg, extra={"category": "LLM"})

def log_error(msg: str):
    logging.error(msg, extra={"category": "ERROR"})


class LLMClient:
    """Client for OpenAI-compatible API endpoints."""

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1", verbose: bool = False):
        """Initialize the LLM client.

        Args:
            api_key: API key for authentication
            base_url: Base URL of the LLM endpoint (e.g., https://api.openai.com/v1 or http://localhost:11434/v1)
            model: **Required** - Model name to use for completions (NO DEFAULT)
            verbose: Whether to enable verbose logging
        """
        if not model:
            raise ValueError("LLM model is required. Set 'model' in booru.conf")
        
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.verbose = verbose
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "reasoning_effort": "low"
            },
            timeout=120.0,
        )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Send a chat completion request to the LLM.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature

        Returns:
            Response from the API containing the assistant's reply

        Raises:
            httpx.HTTPError: If the API request fails
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                log_llm(f"Sending request to {self.base_url} with model {self.model} (attempt {attempt + 1}/{max_retries})")
                response = await self.client.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "messages": messages,
                        "model": self.model
                        # "temperature": temperature,
                    },
                )
                response.raise_for_status()
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                log_llm(f"Response received: {len(content)} chars")
                return result
            except httpx.ReadTimeout as e:
                if attempt == max_retries - 1:
                    log_error(f"LLM API call failed after {max_retries} attempts: ReadTimeout: {e}")
                    raise
                wait_time = 2 ** attempt
                log_llm(f"ReadTimeout, retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            except Exception as e:
                log_error(f"LLM API call failed: {type(e).__name__}: {e}")
                raise
        raise RuntimeError("LLM API call failed after all retries")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
