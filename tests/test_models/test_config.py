"""Tests for configuration models."""

import pytest
from pydantic import ValidationError

from dashboard.models.config import (
    Config,
    FeedConfig,
    LinkCategory,
    LinkItem,
    NetworkConfig,
    NetworkTarget,
    NmapOptions,
    Settings,
    WeatherConfig,
)


class TestFeedConfig:
    """Tests for FeedConfig model."""

    def test_valid_rss_feed(self):
        """Test creating a valid RSS feed config."""
        feed = FeedConfig(
            name="Test Feed",
            url="https://example.com/feed.rss",
            type="rss",
            enabled=True,
        )
        assert feed.name == "Test Feed"
        assert feed.url == "https://example.com/feed.rss"
        assert feed.type == "rss"
        assert feed.enabled is True
        assert feed.json_path is None

    def test_valid_json_feed(self):
        """Test creating a valid JSON feed config."""
        feed = FeedConfig(
            name="JSON Feed",
            url="https://api.example.com/news",
            type="json",
            json_path="$.items[*]",
        )
        assert feed.type == "json"
        assert feed.json_path == "$.items[*]"

    def test_invalid_url_scheme(self):
        """Test that non-http/https URLs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FeedConfig(name="Bad Feed", url="ftp://example.com/feed")
        assert "http or https" in str(exc_info.value)

    def test_invalid_url_no_host(self):
        """Test that URLs without host are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FeedConfig(name="Bad Feed", url="https://")
        assert "Invalid URL" in str(exc_info.value)

    def test_invalid_json_path_unbalanced_brackets(self):
        """Test that invalid JSONPath is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            FeedConfig(
                name="Feed",
                url="https://example.com/api",
                type="json",
                json_path="$.items[0",
            )
        assert "unbalanced brackets" in str(exc_info.value)

    def test_defaults(self):
        """Test default values are applied."""
        feed = FeedConfig(name="Feed", url="https://example.com/feed")
        assert feed.type == "rss"
        assert feed.enabled is True
        assert feed.json_path is None


class TestLinkItem:
    """Tests for LinkItem model."""

    def test_valid_link(self):
        """Test creating a valid link."""
        link = LinkItem(
            name="GitHub",
            url="https://github.com",
            description="Code hosting platform",
        )
        assert link.name == "GitHub"
        assert link.url == "https://github.com"
        assert link.description == "Code hosting platform"

    def test_invalid_url(self):
        """Test that invalid URLs are rejected."""
        with pytest.raises(ValidationError):
            LinkItem(name="Bad", url="not-a-url")

    def test_empty_description_default(self):
        """Test that description defaults to empty string."""
        link = LinkItem(name="Link", url="https://example.com")
        assert link.description == ""

    def test_name_too_long(self):
        """Test that overly long names are rejected."""
        with pytest.raises(ValidationError):
            LinkItem(name="x" * 101, url="https://example.com")


class TestLinkCategory:
    """Tests for LinkCategory model."""

    def test_valid_category(self):
        """Test creating a valid category."""
        category = LinkCategory(
            name="Development",
            links=[
                LinkItem(name="GitHub", url="https://github.com"),
            ],
        )
        assert category.name == "Development"
        assert len(category.links) == 1

    def test_empty_links_default(self):
        """Test that links default to empty list."""
        category = LinkCategory(name="Empty")
        assert category.links == []


class TestNetworkTarget:
    """Tests for NetworkTarget model."""

    def test_valid_cidr(self):
        """Test valid CIDR ranges."""
        target = NetworkTarget(name="Local", range="192.168.1.0/24")
        assert target.range == "192.168.1.0/24"

    def test_valid_cidr_ipv6(self):
        """Test valid IPv6 CIDR range."""
        target = NetworkTarget(name="IPv6", range="fe80::/10")
        assert target.range == "fe80::/10"

    def test_invalid_cidr(self):
        """Test that invalid CIDR is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            NetworkTarget(name="Bad", range="not-a-cidr")
        assert "Invalid CIDR" in str(exc_info.value)

    def test_invalid_cidr_bad_mask(self):
        """Test that invalid mask is rejected."""
        with pytest.raises(ValidationError):
            NetworkTarget(name="Bad", range="192.168.1.0/33")

    def test_expected_hosts_default(self):
        """Test that expected_hosts defaults to empty list."""
        target = NetworkTarget(name="Local", range="192.168.1.0/24")
        assert target.expected_hosts == []


class TestNmapOptions:
    """Tests for NmapOptions model."""

    def test_defaults(self):
        """Test default values."""
        options = NmapOptions()
        assert options.enabled is False
        assert options.port_scan is False
        assert options.service_detection is False
        assert options.ports == "22,80,443,8080"


class TestNetworkConfig:
    """Tests for NetworkConfig model."""

    def test_defaults(self):
        """Test default values."""
        config = NetworkConfig()
        assert config.scanner == "scapy"
        assert config.targets == []
        assert config.scan_interval_minutes == 15
        assert config.dns_timeout_seconds == 1.0
        assert config.arp_timeout_seconds == 3.0


class TestWeatherConfig:
    """Tests for WeatherConfig model."""

    def test_valid_coordinates(self):
        """Test valid coordinates."""
        weather = WeatherConfig(
            location_name="London",
            latitude=51.5074,
            longitude=-0.1278,
        )
        assert weather.latitude == 51.5074
        assert weather.longitude == -0.1278

    def test_invalid_latitude_too_high(self):
        """Test that latitude > 90 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            WeatherConfig(latitude=91, longitude=0)
        assert "between -90 and 90" in str(exc_info.value)

    def test_invalid_latitude_too_low(self):
        """Test that latitude < -90 is rejected."""
        with pytest.raises(ValidationError):
            WeatherConfig(latitude=-91, longitude=0)

    def test_invalid_longitude_too_high(self):
        """Test that longitude > 180 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            WeatherConfig(latitude=0, longitude=181)
        assert "between -180 and 180" in str(exc_info.value)

    def test_invalid_longitude_too_low(self):
        """Test that longitude < -180 is rejected."""
        with pytest.raises(ValidationError):
            WeatherConfig(latitude=0, longitude=-181)

    def test_boundary_values(self):
        """Test boundary coordinate values."""
        # North pole
        weather = WeatherConfig(latitude=90, longitude=0)
        assert weather.latitude == 90

        # South pole
        weather = WeatherConfig(latitude=-90, longitude=0)
        assert weather.latitude == -90

        # Date line
        weather = WeatherConfig(latitude=0, longitude=180)
        assert weather.longitude == 180

        weather = WeatherConfig(latitude=0, longitude=-180)
        assert weather.longitude == -180


class TestSettings:
    """Tests for Settings model."""

    def test_defaults(self):
        """Test default values."""
        settings = Settings()
        assert settings.user_name == ""
        assert settings.refresh_interval_minutes == 15
        assert settings.cache_ttl_minutes == 5
        assert settings.log_level == "INFO"

    def test_valid_log_levels(self):
        """Test all valid log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            settings = Settings(log_level=level)
            assert settings.log_level == level

    def test_invalid_log_level(self):
        """Test that invalid log level is rejected."""
        with pytest.raises(ValidationError):
            Settings(log_level="INVALID")


class TestConfig:
    """Tests for main Config model."""

    def test_load_valid_config(self, sample_config_file):
        """Test loading a valid config file."""
        config = Config.load(sample_config_file)
        assert len(config.feeds) == 1
        assert config.feeds[0].name == "Test Feed"
        assert config.weather.location_name == "London"
        assert config.settings.user_name == "Test User"

    def test_load_nonexistent_file(self, temp_dir):
        """Test that loading nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            Config.load(temp_dir / "nonexistent.json")

    def test_load_or_default_existing(self, sample_config_file):
        """Test load_or_default with existing file."""
        config = Config.load_or_default(sample_config_file)
        assert len(config.feeds) == 1

    def test_load_or_default_nonexistent(self, temp_dir):
        """Test load_or_default with nonexistent file returns default."""
        config = Config.load_or_default(temp_dir / "nonexistent.json")
        assert config.feeds == []
        assert config.links == []

    def test_defaults(self):
        """Test default config values."""
        config = Config()
        assert config.feeds == []
        assert config.links == []
        assert isinstance(config.network, NetworkConfig)
        assert isinstance(config.weather, WeatherConfig)
        assert isinstance(config.settings, Settings)
