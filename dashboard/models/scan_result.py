"""Network scan result models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class HostStatus(str, Enum):
    """Status of a discovered host."""

    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class HostInfo(BaseModel):
    """Information about a discovered network host."""

    ip: str
    mac: str = ""
    hostname: str = ""
    status: HostStatus = HostStatus.UP
    vendor: str = ""
    open_ports: list[int] = Field(default_factory=list)
    is_expected: bool = False  # Whether this host was in expected_hosts
    is_new: bool = False  # Whether this is a newly discovered host

    @property
    def display_name(self) -> str:
        """Return best available name for display."""
        if self.hostname:
            return self.hostname
        if self.vendor:
            return f"{self.ip} ({self.vendor})"
        return self.ip


class ScanResult(BaseModel):
    """Result of a network scan."""

    target_name: str
    target_range: str
    hosts: list[HostInfo] = Field(default_factory=list)
    scan_time: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = 0.0
    error: str | None = None

    @property
    def hosts_up(self) -> int:
        """Count of hosts that are up."""
        return sum(1 for h in self.hosts if h.status == HostStatus.UP)

    @property
    def hosts_down(self) -> int:
        """Count of expected hosts that are down."""
        return sum(1 for h in self.hosts if h.status == HostStatus.DOWN)

    @property
    def new_hosts(self) -> list[HostInfo]:
        """List of newly discovered hosts."""
        return [h for h in self.hosts if h.is_new]
