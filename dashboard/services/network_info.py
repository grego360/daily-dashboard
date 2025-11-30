"""Network info service for IP detection and speed testing."""

import asyncio
import json
import logging
import random
import shutil
import socket
import subprocess

import httpx

logger = logging.getLogger(__name__)

# Timeout for HTTP requests
HTTP_TIMEOUT = 10.0

# Timeout for speed test (it can take 30-60 seconds)
SPEEDTEST_TIMEOUT = 90.0

# Retry configuration
MAX_RETRIES = 2
INITIAL_BACKOFF = 0.5
BACKOFF_MULTIPLIER = 2.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _calculate_backoff(attempt: int) -> float:
    """Calculate backoff time with jitter."""
    backoff = INITIAL_BACKOFF * (BACKOFF_MULTIPLIER**attempt)
    jitter = 0.5 + random.random() * 0.5
    return backoff * jitter


class SpeedTestResult:
    """Result of a speed test."""

    def __init__(
        self,
        download_mbps: float = 0.0,
        upload_mbps: float = 0.0,
        ping_ms: float = 0.0,
        server_name: str = "",
        server_location: str = "",
        isp: str = "",
        error: str | None = None,
    ):
        self.download_mbps = download_mbps
        self.upload_mbps = upload_mbps
        self.ping_ms = ping_ms
        self.server_name = server_name
        self.server_location = server_location
        self.isp = isp
        self.error = error

    @property
    def is_success(self) -> bool:
        return self.error is None


class NetworkInfo:
    """Service to get network information."""

    def __init__(self):
        self._speedtest_available: bool | None = None

    def is_speedtest_available(self) -> bool:
        """Check if speedtest-cli is installed."""
        if self._speedtest_available is None:
            self._speedtest_available = shutil.which("speedtest-cli") is not None
        return self._speedtest_available

    def get_local_ip(self) -> str | None:
        """Get the local/LAN IP address."""
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2.0)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except Exception as e:
            logger.debug(f"Failed to get local IP: {e}")
            return None
        finally:
            if s:
                s.close()

    def get_gateway_ip(self) -> str | None:
        """Get the default gateway IP address."""
        try:
            # macOS/Linux: parse netstat output
            result = subprocess.run(
                ["netstat", "-nr"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            for line in result.stdout.splitlines():
                if "default" in line.lower() or line.startswith("0.0.0.0"):
                    parts = line.split()
                    if len(parts) >= 2:
                        gateway = parts[1]
                        # Validate it looks like an IP
                        if gateway.count(".") == 3:
                            return gateway
        except Exception as e:
            logger.debug(f"Failed to get gateway IP: {e}")
        return None

    def get_dns_servers(self) -> list[str]:
        """Get configured DNS servers."""
        dns_servers = []
        try:
            # Try scutil on macOS first (more reliable)
            result = subprocess.run(
                ["scutil", "--dns"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("nameserver["):
                        # Format: "nameserver[0] : 8.8.8.8"
                        parts = line.split(":")
                        if len(parts) >= 2:
                            dns = parts[1].strip()
                            if dns and dns not in dns_servers:
                                dns_servers.append(dns)
                if dns_servers:
                    return dns_servers[:3]  # Limit to first 3
        except Exception as e:
            logger.debug(f"scutil failed: {e}")

        # Fallback to /etc/resolv.conf
        try:
            with open("/etc/resolv.conf") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("nameserver"):
                        parts = line.split()
                        if len(parts) >= 2:
                            dns = parts[1]
                            if dns not in dns_servers:
                                dns_servers.append(dns)
        except Exception as e:
            logger.debug(f"Failed to read resolv.conf: {e}")

        return dns_servers[:3]  # Limit to first 3

    async def get_public_ip(self) -> str | None:
        """Get the public/internet-facing IP address with retry logic."""
        # Try multiple services in case one fails
        services = [
            "https://api.ipify.org?format=json",
            "https://api.my-ip.io/v2/ip.json",
            "https://ipinfo.io/json",
        ]

        for url in services:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                        response = await client.get(url)
                        response.raise_for_status()
                        data = response.json()
                        # Different services use different keys
                        ip = data.get("ip") or data.get("origin")
                        if ip:
                            return ip
                        break  # No IP in response, try next service

                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    if status in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                        backoff = _calculate_backoff(attempt)
                        logger.debug(
                            f"Public IP HTTP {status}, retry {attempt + 1} in {backoff:.1f}s"
                        )
                        await asyncio.sleep(backoff)
                        continue
                    logger.debug(f"Failed to get public IP from {url}: HTTP {status}")
                    break  # Non-retryable error, try next service

                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    if attempt < MAX_RETRIES:
                        backoff = _calculate_backoff(attempt)
                        logger.debug(f"Public IP error, retry {attempt + 1} in {backoff:.1f}s")
                        await asyncio.sleep(backoff)
                        continue
                    logger.debug(f"Failed to get public IP from {url}: {e}")
                    break  # Exhausted retries, try next service

                except Exception as e:
                    logger.debug(f"Failed to get public IP from {url}: {e}")
                    break  # Unknown error, try next service

        return None

    async def run_speedtest(self) -> SpeedTestResult:
        """Run speed test using speedtest-cli."""
        if not self.is_speedtest_available():
            return SpeedTestResult(error="Install speedtest-cli: brew install speedtest-cli")

        try:
            # Run speedtest CLI in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._run_speedtest_cli),
                timeout=SPEEDTEST_TIMEOUT,
            )
            return result

        except TimeoutError:
            return SpeedTestResult(error="Speed test timed out")
        except Exception as e:
            logger.error(f"Speed test error: {e}")
            return SpeedTestResult(error=str(e))

    def _run_speedtest_cli(self) -> SpeedTestResult:
        """Run speedtest-cli (blocking - call from executor)."""
        try:
            result = subprocess.run(
                ["speedtest-cli", "--json"],
                check=False,
                capture_output=True,
                text=True,
                timeout=SPEEDTEST_TIMEOUT,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or "speedtest failed"
                return SpeedTestResult(error=error_msg)

            data = json.loads(result.stdout)

            # Parse results - speedtest-cli gives bits/sec
            download_bps = data.get("download", 0)
            upload_bps = data.get("upload", 0)
            ping_ms = data.get("ping", 0)

            # Convert bits/sec to Mbps (divide by 1,000,000)
            download_mbps = download_bps / 1_000_000
            upload_mbps = upload_bps / 1_000_000

            server = data.get("server", {})
            client = data.get("client", {})

            # Build server location from available fields
            server_location = ""
            if server.get("country"):
                server_location = server.get("country", "")

            return SpeedTestResult(
                download_mbps=round(download_mbps, 1),
                upload_mbps=round(upload_mbps, 1),
                ping_ms=round(ping_ms, 1),
                server_name=server.get("sponsor", "") or server.get("name", ""),
                server_location=server_location,
                isp=client.get("isp", ""),
            )

        except json.JSONDecodeError:
            return SpeedTestResult(error="Failed to parse speedtest output")
        except subprocess.TimeoutExpired:
            return SpeedTestResult(error="Speed test timed out")
        except Exception as e:
            logger.error(f"Speedtest CLI error: {e}")
            return SpeedTestResult(error=str(e))
