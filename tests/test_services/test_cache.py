"""Tests for cache service."""

import time
from pathlib import Path

import pytest

from dashboard.services.cache import Cache


class TestCacheInit:
    """Tests for Cache initialization."""

    def test_creates_cache_directory(self, temp_dir):
        """Test that cache directory is created."""
        cache_dir = temp_dir / "test_cache"
        cache = Cache(cache_dir=cache_dir)
        assert cache_dir.exists()
        assert cache._enabled is True

    def test_uses_existing_directory(self, temp_dir):
        """Test that existing directory is used."""
        cache_dir = temp_dir / "existing"
        cache_dir.mkdir()
        cache = Cache(cache_dir=cache_dir)
        assert cache._enabled is True

    def test_disabled_on_permission_error(self, temp_dir, monkeypatch):
        """Test cache is disabled when directory is not writable."""
        cache_dir = temp_dir / "readonly"
        cache_dir.mkdir()

        # Make touch fail
        def mock_touch(*args, **kwargs):
            raise PermissionError("Permission denied")

        monkeypatch.setattr(Path, "touch", mock_touch)
        cache = Cache(cache_dir=cache_dir)
        assert cache._enabled is False


class TestCacheOperations:
    """Tests for cache get/set operations."""

    @pytest.fixture
    def cache(self, temp_dir):
        """Create a cache instance for testing."""
        return Cache(cache_dir=temp_dir / "cache", ttl_minutes=5)

    def test_set_and_get(self, cache):
        """Test basic set and get operations."""
        cache.set("test_key", {"data": "value"})
        result = cache.get("test_key")
        assert result == {"data": "value"}

    def test_get_nonexistent_key(self, cache):
        """Test getting a key that doesn't exist."""
        result = cache.get("nonexistent")
        assert result is None

    def test_get_expired_key(self, temp_dir):
        """Test that expired keys return None."""
        # Create cache with 0 minute TTL (expired immediately)
        cache = Cache(cache_dir=temp_dir / "cache", ttl_minutes=0)
        cache.set("test_key", {"data": "value"})

        # Need to wait a tiny bit for the TTL check
        time.sleep(0.01)
        result = cache.get("test_key")
        assert result is None

    def test_get_stale_returns_expired_data(self, temp_dir):
        """Test get_stale returns data even when expired."""
        cache = Cache(cache_dir=temp_dir / "cache", ttl_minutes=0)
        cache.set("test_key", {"data": "value"})

        time.sleep(0.01)
        # Regular get should return None (expired)
        assert cache.get("test_key") is None
        # get_stale should return the data
        result = cache.get_stale("test_key")
        assert result == {"data": "value"}

    def test_get_stale_nonexistent(self, cache):
        """Test get_stale on nonexistent key."""
        result = cache.get_stale("nonexistent")
        assert result is None

    def test_set_overwrites(self, cache):
        """Test that set overwrites existing data."""
        cache.set("key", {"version": 1})
        cache.set("key", {"version": 2})
        result = cache.get("key")
        assert result == {"version": 2}

    def test_different_data_types(self, cache):
        """Test caching different JSON-serializable types."""
        test_cases = [
            ("string", "hello"),
            ("number", 42),
            ("float", 3.14),
            ("list", [1, 2, 3]),
            ("nested", {"a": {"b": {"c": 1}}}),
            ("mixed", {"items": [1, "two", 3.0]}),
        ]
        for key, value in test_cases:
            cache.set(key, value)
            assert cache.get(key) == value

    def test_key_sanitization(self, cache):
        """Test that special characters in keys are handled."""
        cache.set("key/with/slashes", {"data": 1})
        cache.set("key:with:colons", {"data": 2})
        cache.set("key with spaces", {"data": 3})

        assert cache.get("key/with/slashes") == {"data": 1}
        assert cache.get("key:with:colons") == {"data": 2}
        assert cache.get("key with spaces") == {"data": 3}


class TestCacheClear:
    """Tests for cache clearing operations."""

    @pytest.fixture
    def cache(self, temp_dir):
        """Create a cache instance with some data."""
        cache = Cache(cache_dir=temp_dir / "cache", ttl_minutes=5)
        cache.set("key1", {"data": 1})
        cache.set("key2", {"data": 2})
        cache.set("key3", {"data": 3})
        return cache

    def test_clear_specific_key(self, cache):
        """Test clearing a specific cache entry."""
        cache.clear("key1")
        assert cache.get("key1") is None
        assert cache.get("key2") == {"data": 2}
        assert cache.get("key3") == {"data": 3}

    def test_clear_nonexistent_key(self, cache):
        """Test clearing a key that doesn't exist (should not error)."""
        cache.clear("nonexistent")  # Should not raise

    def test_clear_all(self, cache):
        """Test clearing all cache entries."""
        cache.clear_all()
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None


class TestDisabledCache:
    """Tests for disabled cache behavior."""

    @pytest.fixture
    def disabled_cache(self, temp_dir):
        """Create a disabled cache instance."""
        cache = Cache(cache_dir=temp_dir / "cache")
        cache._enabled = False
        return cache

    def test_set_does_nothing(self, disabled_cache):
        """Test that set does nothing when disabled."""
        disabled_cache.set("key", {"data": "value"})
        # Even with enabled cache reading, should be None
        disabled_cache._enabled = True
        assert disabled_cache.get("key") is None

    def test_get_returns_none(self, disabled_cache):
        """Test that get returns None when disabled."""
        # Pre-populate while enabled
        disabled_cache._enabled = True
        disabled_cache.set("key", {"data": "value"})
        disabled_cache._enabled = False

        assert disabled_cache.get("key") is None

    def test_get_stale_returns_none(self, disabled_cache):
        """Test that get_stale returns None when disabled."""
        disabled_cache._enabled = True
        disabled_cache.set("key", {"data": "value"})
        disabled_cache._enabled = False

        assert disabled_cache.get_stale("key") is None


class TestCacheCorruption:
    """Tests for handling corrupted cache files."""

    @pytest.fixture
    def cache(self, temp_dir):
        """Create a cache instance."""
        return Cache(cache_dir=temp_dir / "cache", ttl_minutes=5)

    def test_corrupted_data_file(self, cache):
        """Test handling of corrupted JSON data file."""
        cache.set("key", {"data": "value"})

        # Corrupt the data file
        path = cache._get_path("key")
        with open(path, "w") as f:
            f.write("not valid json {{{")

        result = cache.get("key")
        assert result is None

    def test_corrupted_meta_file(self, cache):
        """Test handling of corrupted metadata file."""
        cache.set("key", {"data": "value"})

        # Corrupt the meta file
        meta_path = cache._get_meta_path("key")
        with open(meta_path, "w") as f:
            f.write("not valid json")

        result = cache.get("key")
        assert result is None

    def test_missing_meta_file(self, cache):
        """Test handling when meta file is missing."""
        cache.set("key", {"data": "value"})

        # Remove the meta file
        meta_path = cache._get_meta_path("key")
        meta_path.unlink()

        result = cache.get("key")
        assert result is None

    def test_get_stale_corrupted_file(self, cache):
        """Test get_stale with corrupted data file."""
        cache.set("key", {"data": "value"})

        path = cache._get_path("key")
        with open(path, "w") as f:
            f.write("corrupted")

        result = cache.get_stale("key")
        assert result is None
