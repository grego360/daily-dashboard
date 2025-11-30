"""Pytest configuration and fixtures."""

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config_data():
    """Sample configuration data for testing."""
    return {
        "feeds": [
            {
                "name": "Test Feed",
                "url": "https://example.com/feed.rss",
                "type": "rss",
                "enabled": True,
            }
        ],
        "links": [
            {
                "name": "Development",
                "links": [
                    {
                        "name": "GitHub",
                        "url": "https://github.com",
                        "description": "Code hosting",
                    }
                ],
            }
        ],
        "network": {
            "scanner": "scapy",
            "targets": [
                {
                    "name": "Local",
                    "range": "192.168.1.0/24",
                    "expected_hosts": ["192.168.1.1"],
                }
            ],
        },
        "weather": {
            "enabled": True,
            "location_name": "London",
            "latitude": 51.5074,
            "longitude": -0.1278,
        },
        "settings": {
            "user_name": "Test User",
            "refresh_interval_minutes": 15,
            "cache_ttl_minutes": 5,
            "log_level": "INFO",
        },
    }


@pytest.fixture
def sample_config_file(temp_dir, sample_config_data):
    """Create a sample config file for testing."""
    config_path = temp_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(sample_config_data, f)
    return config_path
