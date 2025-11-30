"""Network scanner service using scapy for ARP-based discovery."""

import asyncio
import logging
import os
import re
import socket
import subprocess
import sys
from datetime import datetime
from typing import TYPE_CHECKING

from ..models.config import NetworkTarget
from ..models.scan_result import HostInfo, HostStatus, ScanResult

if TYPE_CHECKING:
    from .known_hosts import KnownHostsStore

logger = logging.getLogger(__name__)

# mDNS discovery available on macOS (primary), Linux support is limited
_mdns_available = sys.platform == "darwin"

# Lazy-loaded mac-vendor-lookup instance
_mac_lookup_instance: "MacLookup | None" = None
_mac_lookup_initialized = False


def _get_mac_lookup():
    """Lazy-load mac-vendor-lookup to avoid blocking import."""
    global _mac_lookup_instance, _mac_lookup_initialized

    if _mac_lookup_initialized:
        return _mac_lookup_instance

    _mac_lookup_initialized = True
    try:
        from mac_vendor_lookup import MacLookup

        _mac_lookup_instance = MacLookup()
        # Try to update, but don't block if it fails
        try:
            _mac_lookup_instance.update_vendors()
        except Exception:
            pass  # Use cached/bundled data
    except ImportError:
        logger.debug("mac-vendor-lookup not installed, using fallback vendor list")
        _mac_lookup_instance = None

    return _mac_lookup_instance


class NetworkScanner:
    """ARP-based network scanner using scapy."""

    def __init__(
        self,
        arp_timeout: float = 3.0,
        dns_timeout: float = 1.0,
        known_hosts_store: "KnownHostsStore | None" = None,
    ):
        self.arp_timeout = arp_timeout
        self.dns_timeout = dns_timeout
        self.known_hosts_store = known_hosts_store
        self._scapy_available = self._check_scapy()
        self._has_privileges = self._check_privileges()

    def _check_scapy(self) -> bool:
        """Check if scapy is available and has required permissions."""
        try:
            from scapy.all import conf

            return True
        except ImportError:
            logger.warning("scapy not installed - network scanning disabled")
            return False
        except Exception as e:
            logger.warning(f"scapy error: {e}")
            return False

    def _check_privileges(self) -> bool:
        """Check if we have root/admin privileges for raw socket access."""
        # On Unix-like systems, check for root (uid 0)
        if hasattr(os, "geteuid"):
            return os.geteuid() == 0
        # On Windows, we'd need to check differently, but scapy handles this
        return True

    @property
    def has_privileges(self) -> bool:
        """Return whether we have sufficient privileges for scanning."""
        return self._has_privileges

    @property
    def available(self) -> bool:
        """Return whether network scanning is available."""
        return self._scapy_available and self._has_privileges

    def get_status_message(self) -> str | None:
        """Get a status message about scanner availability."""
        if not self._scapy_available:
            return "scapy not installed - network scanning disabled"
        if not self._has_privileges:
            return "Run with sudo for network scanning"
        return None

    async def scan(self, target: NetworkTarget) -> ScanResult:
        """Scan a network target and return results."""
        start_time = datetime.now()

        if not self._scapy_available:
            return ScanResult(
                target_name=target.name,
                target_range=target.range,
                error="scapy not available",
                scan_time=start_time,
            )

        try:
            # Run scapy scan in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            hosts = await loop.run_in_executor(None, self._arp_scan, target.range)

            # Resolve hostnames
            hosts = await self._resolve_hostnames(hosts)

            # Mark expected hosts
            hosts = self._mark_expected_hosts(hosts, target.expected_hosts)

            duration = (datetime.now() - start_time).total_seconds()

            return ScanResult(
                target_name=target.name,
                target_range=target.range,
                hosts=hosts,
                scan_time=start_time,
                duration_seconds=duration,
            )

        except PermissionError:
            return ScanResult(
                target_name=target.name,
                target_range=target.range,
                error="Permission denied - run with sudo for network scanning",
                scan_time=start_time,
            )
        except Exception as e:
            logger.error(f"Scan error for {target.name}: {e}")
            return ScanResult(
                target_name=target.name,
                target_range=target.range,
                error=str(e),
                scan_time=start_time,
            )

    def _arp_scan(self, network: str) -> list[HostInfo]:
        """Perform ARP scan on the network (runs in thread pool)."""
        from scapy.all import ARP, Ether, conf, srp

        # Suppress scapy warnings
        conf.verb = 0

        arp = ARP(pdst=network)
        ether = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = ether / arp

        result = srp(packet, timeout=self.arp_timeout, verbose=False)[0]

        hosts = []
        for sent, received in result:
            hosts.append(
                HostInfo(
                    ip=received.psrc,
                    mac=received.hwsrc,
                    status=HostStatus.UP,
                    vendor=self._get_vendor(received.hwsrc),
                )
            )

        return hosts

    def _get_vendor(self, mac: str) -> str:
        """Get vendor name from MAC address using mac-vendor-lookup or fallback."""
        # Try mac-vendor-lookup first (has 40K+ vendors)
        mac_lookup = _get_mac_lookup()
        if mac_lookup:
            try:
                vendor = mac_lookup.lookup(mac)
                if vendor:
                    # Shorten common long vendor names
                    vendor = self._shorten_vendor_name(vendor)
                    return vendor
            except Exception:
                pass  # Fall through to fallback

        # Fallback to hardcoded common vendors
        oui_prefix = mac[:8].upper().replace(":", "-")
        fallback_vendors = {
            "00-50-56": "VMware",
            "00-0C-29": "VMware",
            "08-00-27": "VirtualBox",
            "52-54-00": "QEMU",
            "B8-27-EB": "Raspberry Pi",
            "DC-A6-32": "Raspberry Pi",
            "E4-5F-01": "Raspberry Pi",
            "00-17-88": "Philips Hue",
            "EC-B5-FA": "Philips Hue",
        }
        return fallback_vendors.get(oui_prefix, "")

    def _shorten_vendor_name(self, vendor: str) -> str:
        """Shorten common long vendor names for display."""
        # Map of long names to shorter versions
        shortenings = {
            "Apple, Inc.": "Apple",
            "Samsung Electronics Co.,Ltd": "Samsung",
            "Intel Corporate": "Intel",
            "Raspberry Pi Foundation": "Raspberry Pi",
            "Raspberry Pi Trading Ltd": "Raspberry Pi",
            "HUAWEI TECHNOLOGIES CO.,LTD": "Huawei",
            "Amazon Technologies Inc.": "Amazon",
            "Google, Inc.": "Google",
            "Microsoft Corporation": "Microsoft",
            "Sony Corporation": "Sony",
            "LG Electronics": "LG",
            "Xiaomi Communications Co Ltd": "Xiaomi",
            "TP-LINK TECHNOLOGIES CO.,LTD.": "TP-Link",
            "ASUSTek COMPUTER INC.": "ASUS",
            "Hewlett Packard": "HP",
            "Dell Inc.": "Dell",
            "Cisco Systems, Inc": "Cisco",
            "NETGEAR": "Netgear",
            "Belkin International Inc.": "Belkin",
            "Hon Hai Precision Ind. Co.,Ltd.": "Foxconn",
            "Espressif Inc.": "Espressif",
        }
        return shortenings.get(vendor, vendor)

    async def _resolve_hostnames(self, hosts: list[HostInfo]) -> list[HostInfo]:
        """Resolve hostnames for discovered hosts using DNS and mDNS."""
        loop = asyncio.get_running_loop()
        dns_timeout = self.dns_timeout

        # First, try mDNS service discovery to get a map of MAC -> hostname
        mdns_hostnames: dict[str, str] = {}
        if _mdns_available:
            try:
                mdns_hostnames = await asyncio.wait_for(
                    loop.run_in_executor(None, self._discover_mdns_hostnames),
                    timeout=5.0,
                )
                logger.debug(f"mDNS discovered {len(mdns_hostnames)} hostnames")
            except Exception as e:
                logger.debug(f"mDNS discovery failed: {e}")

        async def resolve_one(host: HostInfo) -> HostInfo:
            # Check mDNS discovery results first (by MAC)
            if host.mac and host.mac.lower() in mdns_hostnames:
                host.hostname = mdns_hostnames[host.mac.lower()]
                return host

            # Try standard reverse DNS
            try:
                hostname, _, _ = await asyncio.wait_for(
                    loop.run_in_executor(None, socket.gethostbyaddr, host.ip),
                    timeout=dns_timeout,
                )
                host.hostname = hostname.split(".")[0]  # Use short hostname
                return host
            except TimeoutError:
                logger.debug(f"DNS lookup timeout for {host.ip}")
            except socket.herror:
                pass  # No reverse DNS
            except Exception as e:
                logger.debug(f"DNS lookup error for {host.ip}: {e}")

            return host

        tasks = [resolve_one(host) for host in hosts]
        return await asyncio.gather(*tasks)

    def _discover_mdns_hostnames(self) -> dict[str, str]:
        """Discover hostnames via mDNS service browsing. Returns MAC -> hostname map."""
        hostnames: dict[str, str] = {}

        if sys.platform != "darwin":
            return hostnames

        # Browse _workstation._tcp which includes MAC addresses in the name
        # dns-sd runs indefinitely, so we use subprocess timeout to kill it
        output = ""
        try:
            result = subprocess.run(
                ["dns-sd", "-B", "_workstation._tcp", "local."],
                check=False,
                capture_output=True,
                text=True,
                timeout=3.0,  # Kill after 3 seconds
            )
            output = result.stdout
        except subprocess.TimeoutExpired as e:
            # dns-sd always times out - get partial output from exception
            if e.stdout:
                output = e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout
        except Exception as e:
            logger.debug(f"mDNS workstation discovery failed: {e}")
            return hostnames

        # Parse lines like:
        # "20:42:49.878  Add  3  15 local.  _workstation._tcp.  RPI-Homebridge [dc:a6:32:6e:ec:7c]"
        mac_pattern = re.compile(r"\[([0-9a-f:]{17})\]", re.IGNORECASE)

        for line in output.splitlines():
            if "_workstation._tcp." in line and "[" in line:
                # Extract MAC address
                mac_match = mac_pattern.search(line)
                if mac_match:
                    mac = mac_match.group(1).lower()
                    # Extract hostname (text before the MAC)
                    parts = line.split("_workstation._tcp.")
                    if len(parts) > 1:
                        name_part = parts[1].strip()
                        # Remove the MAC bracket part
                        hostname = re.sub(r"\s*\[[^\]]+\]", "", name_part).strip()
                        if hostname:
                            hostnames[mac] = hostname

        return hostnames

    def _mark_expected_hosts(self, hosts: list[HostInfo], expected: list[str]) -> list[HostInfo]:
        """Mark hosts as expected/new and add missing expected hosts as DOWN."""
        expected_lower = [e.lower() for e in expected]

        # Mark found hosts
        found_expected = set()
        for host in hosts:
            host_identifiers = [
                host.hostname.lower(),
                host.ip,
                host.mac.lower(),
            ]
            for identifier in host_identifiers:
                if identifier in expected_lower:
                    host.is_expected = True
                    found_expected.add(identifier)
                    break

        # Add missing expected hosts as DOWN
        for expected_host in expected:
            if expected_host.lower() not in found_expected:
                hosts.append(
                    HostInfo(
                        ip="",
                        hostname=expected_host,
                        status=HostStatus.DOWN,
                        is_expected=True,
                    )
                )

        # Mark truly new hosts - check against known hosts store
        for host in hosts:
            if host.status == HostStatus.UP and not host.is_expected and host.mac:
                if self.known_hosts_store:
                    # Use persistent store to determine if truly new
                    is_new = self.known_hosts_store.update_host(
                        mac=host.mac,
                        ip=host.ip,
                        hostname=host.hostname,
                        vendor=host.vendor,
                    )
                    host.is_new = is_new
                else:
                    # No store - mark all unexpected as new (original behavior)
                    host.is_new = True
            elif host.status == HostStatus.UP and host.mac and self.known_hosts_store:
                # Update last_seen for expected hosts too
                self.known_hosts_store.update_host(
                    mac=host.mac,
                    ip=host.ip,
                    hostname=host.hostname,
                    vendor=host.vendor,
                )

        return hosts
