"""Known hosts persistence for tracking network device history."""

import json
import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_KNOWN_HOSTS_PATH = "known_hosts.json"


class KnownHost(BaseModel):
    """A previously discovered network host."""

    mac: str
    ip: str = ""
    hostname: str = ""
    vendor: str = ""
    first_seen: datetime = Field(default_factory=datetime.now)
    last_seen: datetime = Field(default_factory=datetime.now)


class KnownHostsStore:
    """Persists known hosts to track new device discovery."""

    def __init__(self, path: Path | str = DEFAULT_KNOWN_HOSTS_PATH):
        self.path = Path(path)
        self._hosts: dict[str, KnownHost] = {}  # Keyed by MAC address
        self._loaded = False

    def load(self) -> None:
        """Load known hosts from file."""
        if not self.path.exists():
            logger.debug(f"No known hosts file at {self.path}")
            self._hosts = {}
            self._loaded = True
            return

        try:
            with open(self.path) as f:
                data = json.load(f)

            self._hosts = {}
            for mac, host_data in data.get("hosts", {}).items():
                try:
                    self._hosts[mac.lower()] = KnownHost(**host_data)
                except Exception as e:
                    logger.warning(f"Invalid host entry for {mac}: {e}")

            logger.debug(f"Loaded {len(self._hosts)} known hosts")
            self._loaded = True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in known hosts file: {e}")
            self._hosts = {}
            self._loaded = True
        except Exception as e:
            logger.error(f"Error loading known hosts: {e}")
            self._hosts = {}
            self._loaded = True

    def save(self) -> bool:
        """Save known hosts to file."""
        try:
            data = {
                "hosts": {mac: host.model_dump(mode="json") for mac, host in self._hosts.items()}
            }

            with open(self.path, "w") as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug(f"Saved {len(self._hosts)} known hosts")
            return True

        except Exception as e:
            logger.error(f"Error saving known hosts: {e}")
            return False

    def is_known(self, mac: str) -> bool:
        """Check if a MAC address has been seen before."""
        if not self._loaded:
            self.load()
        return mac.lower() in self._hosts

    def get_host(self, mac: str) -> KnownHost | None:
        """Get a known host by MAC address."""
        if not self._loaded:
            self.load()
        return self._hosts.get(mac.lower())

    def update_host(
        self,
        mac: str,
        ip: str = "",
        hostname: str = "",
        vendor: str = "",
    ) -> bool:
        """Update or add a host. Returns True if this is a new host."""
        if not self._loaded:
            self.load()

        mac_lower = mac.lower()
        now = datetime.now()

        if mac_lower in self._hosts:
            # Update existing host
            host = self._hosts[mac_lower]
            if ip:
                host.ip = ip
            if hostname:
                host.hostname = hostname
            if vendor:
                host.vendor = vendor
            host.last_seen = now
            return False  # Not new
        else:
            # Add new host
            self._hosts[mac_lower] = KnownHost(
                mac=mac_lower,
                ip=ip,
                hostname=hostname,
                vendor=vendor,
                first_seen=now,
                last_seen=now,
            )
            return True  # Is new

    def get_all_hosts(self) -> dict[str, KnownHost]:
        """Get all known hosts."""
        if not self._loaded:
            self.load()
        return self._hosts.copy()

    @property
    def count(self) -> int:
        """Number of known hosts."""
        if not self._loaded:
            self.load()
        return len(self._hosts)
