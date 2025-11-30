"""Configuration models using Pydantic for validation."""

import ipaddress
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class FeedConfig(BaseModel):
    """Configuration for a single news feed."""

    name: str
    url: str
    type: Literal["rss", "json"] = "rss"
    enabled: bool = True
    json_path: str | None = None  # JSONPath for extracting items from JSON feeds

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that URL is a valid HTTP/HTTPS URL."""
        try:
            parsed = urlparse(v)
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"URL must use http or https scheme, got '{parsed.scheme}'")
            if not parsed.netloc:
                raise ValueError("URL must have a valid host")
        except Exception as e:
            raise ValueError(f"Invalid URL '{v}': {e}")
        return v

    @field_validator("json_path")
    @classmethod
    def validate_json_path(cls, v: str | None) -> str | None:
        """Basic validation of JSONPath expression."""
        if not v:
            return v
        if v.count("[") != v.count("]"):
            raise ValueError("Invalid JSONPath: unbalanced brackets")
        return v


class LinkItem(BaseModel):
    """A single saved link."""

    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., max_length=2000)
    description: str = Field(default="", max_length=500)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that URL is a valid HTTP/HTTPS URL."""
        try:
            parsed = urlparse(v)
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"URL must use http or https scheme, got '{parsed.scheme}'")
            if not parsed.netloc:
                raise ValueError("URL must have a valid host")
        except Exception as e:
            raise ValueError(f"Invalid URL '{v}': {e}")
        return v


class LinkCategory(BaseModel):
    """A category/group of links."""

    name: str = Field(..., min_length=1, max_length=50)
    links: list[LinkItem] = Field(default_factory=list)


class NetworkTarget(BaseModel):
    """Configuration for a network scan target."""

    name: str
    range: str  # CIDR notation, e.g., "192.168.1.0/24"
    expected_hosts: list[str] = Field(default_factory=list)

    @field_validator("range")
    @classmethod
    def validate_cidr(cls, v: str) -> str:
        """Validate that range is a valid CIDR notation."""
        try:
            ipaddress.ip_network(v, strict=False)
        except ValueError as e:
            raise ValueError(f"Invalid CIDR range '{v}': {e}")
        return v


class NmapOptions(BaseModel):
    """Optional nmap configuration for advanced scanning."""

    enabled: bool = False
    port_scan: bool = False
    service_detection: bool = False
    ports: str = "22,80,443,8080"  # Default ports to scan


class NetworkConfig(BaseModel):
    """Network scanning configuration."""

    scanner: Literal["scapy", "nmap"] = "scapy"
    targets: list[NetworkTarget] = Field(default_factory=list)
    scan_interval_minutes: int = 15
    dns_timeout_seconds: float = 1.0  # Timeout for DNS reverse lookups (0.5-2.0 recommended)
    arp_timeout_seconds: float = 3.0  # Timeout for ARP scan
    nmap_options: NmapOptions = Field(default_factory=NmapOptions)


class WeatherConfig(BaseModel):
    """Weather configuration."""

    enabled: bool = True
    location_name: str = "Berlin"
    latitude: float = 52.52
    longitude: float = 13.41

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        """Validate latitude is in valid range."""
        if not -90 <= v <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {v}")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        """Validate longitude is in valid range."""
        if not -180 <= v <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {v}")
        return v


class Settings(BaseModel):
    """General application settings."""

    user_name: str = ""
    refresh_interval_minutes: int = 15
    cache_ttl_minutes: int = 5
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


class Config(BaseModel):
    """Main configuration model."""

    feeds: list[FeedConfig] = Field(default_factory=list)
    links: list[LinkCategory] = Field(default_factory=list)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    weather: WeatherConfig = Field(default_factory=WeatherConfig)
    settings: Settings = Field(default_factory=Settings)

    @classmethod
    def load(cls, path: Path | str = "config.json") -> "Config":
        """Load configuration from a JSON file."""
        import json

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path) as f:
            data = json.load(f)

        return cls.model_validate(data)

    @classmethod
    def load_or_default(cls, path: Path | str = "config.json") -> "Config":
        """Load configuration or return default if file doesn't exist."""
        try:
            return cls.load(path)
        except FileNotFoundError:
            return cls()
