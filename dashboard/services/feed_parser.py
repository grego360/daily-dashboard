"""Feed parser service for RSS and JSON feeds."""

import asyncio
import json
import logging
import random
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx

from ..models.config import FeedConfig
from ..models.news_item import NewsItem

logger = logging.getLogger(__name__)

# Rate limiting: max concurrent requests
MAX_CONCURRENT_REQUESTS = 3

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
MAX_BACKOFF = 10.0  # seconds
BACKOFF_MULTIPLIER = 2.0

# HTTP status codes that should trigger a retry
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class FeedParser:
    """Async feed parser supporting RSS and JSON formats."""

    def __init__(
        self,
        timeout: float = 30.0,
        max_items: int = 50,
        max_retries: int = MAX_RETRIES,
    ):
        self.timeout = timeout
        self.max_items = max_items
        self.max_retries = max_retries
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "FeedParser":
        """Create shared HTTP client for connection pooling."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=10.0),
            follow_redirects=True,
            headers={"User-Agent": "MorningDashboard/1.0"},
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Close shared HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_feed(self, config: FeedConfig) -> list[NewsItem]:
        """Fetch and parse a feed based on its configuration."""
        if not config.enabled:
            return []

        # Rate limiting
        async with self._semaphore:
            return await self._fetch_feed_impl(config)

    async def _fetch_feed_impl(self, config: FeedConfig) -> list[NewsItem]:
        """Internal implementation of feed fetching with retry logic."""
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self._make_request(config.url)
                response.raise_for_status()

                if config.type == "rss":
                    return self._parse_rss(response.text, config.name)
                else:
                    try:
                        data = response.json()
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON from {config.name}: {e}")
                        return []
                    return self._parse_json(data, config)

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.debug(
                        f"Timeout for '{config.name}', retry {attempt + 1} in {backoff:.1f}s"
                    )
                    await asyncio.sleep(backoff)
                    continue
                logger.warning(
                    f"Timeout fetching feed '{config.name}' after {self.max_retries + 1} attempts"
                )
                return []

            except httpx.ConnectError as e:
                last_error = e
                if attempt < self.max_retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.debug(
                        f"Connection error for '{config.name}', retry {attempt + 1} in {backoff:.1f}s"
                    )
                    await asyncio.sleep(backoff)
                    continue
                logger.warning(f"Connection error for '{config.name}': {e} - check network")
                return []

            except httpx.HTTPStatusError as e:
                status = e.response.status_code

                # Retry on transient errors
                if status in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.debug(
                        f"HTTP {status} from '{config.name}', retry {attempt + 1} in {backoff:.1f}s"
                    )
                    await asyncio.sleep(backoff)
                    continue

                # Log non-retryable or exhausted retries
                if status == 429:
                    logger.warning(f"Rate limited by '{config.name}' - reduce refresh frequency")
                elif status >= 500:
                    logger.warning(f"Server error {status} from '{config.name}' after retries")
                elif status == 404:
                    logger.error(f"Feed '{config.name}' not found (404) - check URL")
                elif status == 403:
                    logger.error(f"Access denied to '{config.name}' (403) - may need auth")
                else:
                    logger.error(f"HTTP {status} from '{config.name}'")
                return []

            except httpx.RequestError as e:
                last_error = e
                if attempt < self.max_retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.debug(
                        f"Request error for '{config.name}', retry {attempt + 1} in {backoff:.1f}s"
                    )
                    await asyncio.sleep(backoff)
                    continue
                logger.error(f"Request error for '{config.name}': {type(e).__name__}")
                return []

            except Exception as e:
                logger.error(f"Unexpected error fetching '{config.name}': {type(e).__name__}: {e}")
                return []

        return []

    async def _make_request(self, url: str) -> httpx.Response:
        """Make HTTP request using shared or new client."""
        if self._client:
            return await self._client.get(str(url))
        else:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                follow_redirects=True,
                headers={"User-Agent": "MorningDashboard/1.0"},
            ) as client:
                return await client.get(str(url))

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate backoff time with jitter."""
        backoff = min(INITIAL_BACKOFF * (BACKOFF_MULTIPLIER**attempt), MAX_BACKOFF)
        # Add jitter (0.5 to 1.5 multiplier)
        jitter = 0.5 + random.random()
        return backoff * jitter

    def _parse_rss(self, content: str, source: str) -> list[NewsItem]:
        """Parse RSS/Atom feed content."""
        try:
            feed = feedparser.parse(content)
        except Exception as e:
            logger.error(f"Failed to parse RSS from {source}: {e}")
            return []

        if feed.bozo and feed.bozo_exception:
            logger.warning(f"RSS parse warning for {source}: {feed.bozo_exception}")

        items = []
        for entry in feed.entries[: self.max_items]:
            try:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6], tzinfo=UTC)

                items.append(
                    NewsItem(
                        title=entry.get("title", "Untitled"),
                        url=entry.get("link", ""),
                        published=published,
                        source=source,
                        summary=entry.get("summary", "")[:200] if entry.get("summary") else "",
                    )
                )
            except Exception as e:
                logger.debug(f"Skipping malformed entry in {source}: {e}")
                continue

        if len(feed.entries) > self.max_items:
            logger.debug(f"Feed {source} has {len(feed.entries)} items, showing {self.max_items}")

        return items

    def _parse_json(self, data: dict[str, Any], config: FeedConfig) -> list[NewsItem]:
        """Parse JSON feed content using json_path if provided."""
        items_data: Any = data

        # Navigate to items using json_path (simplified implementation)
        if config.json_path:
            try:
                parts = config.json_path.replace("[*]", "").split(".")
                for part in parts:
                    if part and isinstance(items_data, dict):
                        items_data = items_data.get(part, [])
                    elif part and isinstance(items_data, list) and items_data:
                        items_data = [
                            item.get(part, item) for item in items_data if isinstance(item, dict)
                        ]
            except Exception as e:
                logger.error(
                    f"Failed to navigate json_path '{config.json_path}' for {config.name}: {e}"
                )
                return []

        if not isinstance(items_data, list):
            items_data = [items_data]

        if not items_data:
            logger.warning(f"No items found in JSON feed '{config.name}' - check json_path")
            return []

        items = []
        for item in items_data[: self.max_items]:
            if not isinstance(item, dict):
                continue

            try:
                # Try common field names
                title = item.get("title") or item.get("headline") or item.get("name") or "Untitled"
                url = item.get("url") or item.get("link") or item.get("permalink") or ""

                # Skip items without title
                if title == "Untitled" and not url:
                    continue

                published = None
                for date_field in ["published", "created", "date", "created_utc", "timestamp"]:
                    if date_field in item:
                        published = self._parse_date(item[date_field])
                        if published:
                            break

                summary = (
                    item.get("summary") or item.get("description") or item.get("selftext") or ""
                )

                items.append(
                    NewsItem(
                        title=str(title),
                        url=str(url),
                        published=published,
                        source=config.name,
                        summary=str(summary)[:200],
                    )
                )
            except Exception as e:
                logger.debug(f"Skipping malformed item in {config.name}: {e}")
                continue

        return items

    def _parse_date(self, value: Any) -> datetime | None:
        """Parse various date formats."""
        if value is None:
            return None

        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value, tz=UTC)
            except (ValueError, OSError):
                return None

        if isinstance(value, str):
            for fmt in [
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]:
                try:
                    return datetime.strptime(value, fmt).replace(tzinfo=UTC)
                except ValueError:
                    continue

        return None
