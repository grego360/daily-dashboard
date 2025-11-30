"""Optional nmap scanner for advanced network scanning features."""

import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime

from ..models.config import NetworkTarget, NmapOptions
from ..models.scan_result import HostInfo, HostStatus, ScanResult

logger = logging.getLogger(__name__)


class NmapScanner:
    """Advanced network scanner using nmap (optional)."""

    def __init__(self):
        self._nmap_available = self._check_nmap()

    def _check_nmap(self) -> bool:
        """Check if nmap is installed."""
        import shutil

        return shutil.which("nmap") is not None

    @property
    def available(self) -> bool:
        """Check if nmap is available for scanning."""
        return self._nmap_available

    async def scan(self, target: NetworkTarget, options: NmapOptions) -> ScanResult:
        """Run nmap scan with specified options."""
        start_time = datetime.now()

        if not self._nmap_available:
            return ScanResult(
                target_name=target.name,
                target_range=target.range,
                error="nmap not installed",
                scan_time=start_time,
            )

        try:
            # Build nmap command
            cmd = self._build_command(target.range, options)
            logger.debug(f"Running nmap: {' '.join(cmd)}")

            # Run nmap asynchronously
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode().strip() or f"nmap exited with code {process.returncode}"
                return ScanResult(
                    target_name=target.name,
                    target_range=target.range,
                    error=error_msg,
                    scan_time=start_time,
                )

            # Parse XML output
            hosts = self._parse_xml(stdout.decode())
            duration = (datetime.now() - start_time).total_seconds()

            return ScanResult(
                target_name=target.name,
                target_range=target.range,
                hosts=hosts,
                scan_time=start_time,
                duration_seconds=duration,
            )

        except FileNotFoundError:
            return ScanResult(
                target_name=target.name,
                target_range=target.range,
                error="nmap not found in PATH",
                scan_time=start_time,
            )
        except Exception as e:
            logger.error(f"Nmap scan error: {e}")
            return ScanResult(
                target_name=target.name,
                target_range=target.range,
                error=str(e),
                scan_time=start_time,
            )

    def _build_command(self, target: str, options: NmapOptions) -> list[str]:
        """Build nmap command with appropriate flags."""
        cmd = ["nmap", "-oX", "-"]  # XML output to stdout

        if options.port_scan:
            cmd.extend(["-sT", "-p", options.ports])
        else:
            cmd.append("-sn")  # Ping scan only

        if options.service_detection:
            cmd.append("-sV")

        cmd.append(target)
        return cmd

    def _parse_xml(self, xml_content: str) -> list[HostInfo]:
        """Parse nmap XML output."""
        hosts = []

        try:
            root = ET.fromstring(xml_content)

            for host_elem in root.findall(".//host"):
                status_elem = host_elem.find("status")
                if status_elem is None:
                    continue

                status_str = status_elem.get("state", "unknown")
                status = HostStatus.UP if status_str == "up" else HostStatus.DOWN

                # Get IP address
                ip = ""
                mac = ""
                vendor = ""
                for addr in host_elem.findall("address"):
                    if addr.get("addrtype") == "ipv4":
                        ip = addr.get("addr", "")
                    elif addr.get("addrtype") == "mac":
                        mac = addr.get("addr", "")
                        vendor = addr.get("vendor", "")

                # Get hostname
                hostname = ""
                hostnames_elem = host_elem.find("hostnames")
                if hostnames_elem is not None:
                    hostname_elem = hostnames_elem.find("hostname")
                    if hostname_elem is not None:
                        hostname = hostname_elem.get("name", "")

                # Get open ports
                open_ports = []
                ports_elem = host_elem.find("ports")
                if ports_elem is not None:
                    for port in ports_elem.findall("port"):
                        state = port.find("state")
                        if state is not None and state.get("state") == "open":
                            port_id = port.get("portid")
                            if port_id:
                                open_ports.append(int(port_id))

                hosts.append(
                    HostInfo(
                        ip=ip,
                        mac=mac,
                        hostname=hostname,
                        status=status,
                        vendor=vendor,
                        open_ports=open_ports,
                    )
                )

        except ET.ParseError as e:
            logger.error(f"Failed to parse nmap XML: {e}")

        return hosts
