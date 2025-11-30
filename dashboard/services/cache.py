"""Simple file-based cache for feeds and scan results."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Cache:
    """File-based cache with TTL support."""

    def __init__(self, cache_dir: Path | str = ".cache", ttl_minutes: int = 5):
        self.cache_dir = Path(cache_dir)
        self.ttl = timedelta(minutes=ttl_minutes)
        self._enabled = True

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # Test write permission
            test_file = self.cache_dir / ".test"
            test_file.touch()
            test_file.unlink()
        except (PermissionError, OSError) as e:
            logger.warning(f"Cache disabled - cannot write to {cache_dir}: {e}")
            self._enabled = False

    def _get_path(self, key: str) -> Path:
        """Get cache file path for a key."""
        safe_key = "".join(c if c.isalnum() else "_" for c in key)
        return self.cache_dir / f"{safe_key}.json"

    def _get_meta_path(self, key: str) -> Path:
        """Get metadata file path for a key."""
        safe_key = "".join(c if c.isalnum() else "_" for c in key)
        return self.cache_dir / f"{safe_key}.meta"

    def get(self, key: str) -> Any | None:
        """Get cached value if it exists and hasn't expired."""
        if not self._enabled:
            return None

        path = self._get_path(key)
        meta_path = self._get_meta_path(key)

        if not path.exists() or not meta_path.exists():
            return None

        try:
            with open(meta_path) as f:
                meta = json.load(f)
                cached_at = datetime.fromisoformat(meta["cached_at"])

            if datetime.now() - cached_at > self.ttl:
                logger.debug(f"Cache expired for {key}")
                return None

            with open(path) as f:
                return json.load(f)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to read cache for {key}: {e}")
            return None

    def get_stale(self, key: str) -> Any | None:
        """Get cached value even if expired (for showing stale data while refreshing)."""
        if not self._enabled:
            return None

        path = self._get_path(key)

        if not path.exists():
            return None

        try:
            with open(path) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to read stale cache for {key}: {e}")
            return None

    def set(self, key: str, value: Any) -> None:
        """Cache a value."""
        if not self._enabled:
            return

        path = self._get_path(key)
        meta_path = self._get_meta_path(key)

        try:
            with open(path, "w") as f:
                json.dump(value, f)

            with open(meta_path, "w") as f:
                json.dump({"cached_at": datetime.now().isoformat()}, f)

            logger.debug(f"Cached {key}")

        except (TypeError, OSError) as e:
            logger.warning(f"Failed to cache {key}: {e}")

    def clear(self, key: str) -> None:
        """Clear a specific cache entry."""
        path = self._get_path(key)
        meta_path = self._get_meta_path(key)

        path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)

    def clear_all(self) -> None:
        """Clear all cached data."""
        for path in self.cache_dir.glob("*.json"):
            path.unlink(missing_ok=True)
        for path in self.cache_dir.glob("*.meta"):
            path.unlink(missing_ok=True)
