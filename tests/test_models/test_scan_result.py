"""Tests for scan result models."""

import pytest

from dashboard.models.scan_result import HostInfo, HostStatus, ScanResult


class TestHostStatus:
    """Tests for HostStatus enum."""

    def test_values(self):
        """Test enum values."""
        assert HostStatus.UP.value == "up"
        assert HostStatus.DOWN.value == "down"
        assert HostStatus.UNKNOWN.value == "unknown"

    def test_string_enum(self):
        """Test that HostStatus is a string enum."""
        assert HostStatus.UP.value == "up"
        # String enums can be compared directly with strings
        assert HostStatus.UP == "up"


class TestHostInfo:
    """Tests for HostInfo model."""

    def test_basic_creation(self):
        """Test creating a basic host info."""
        host = HostInfo(ip="192.168.1.1")
        assert host.ip == "192.168.1.1"
        assert host.mac == ""
        assert host.hostname == ""
        assert host.status == HostStatus.UP
        assert host.vendor == ""
        assert host.open_ports == []
        assert host.is_expected is False
        assert host.is_new is False

    def test_full_host_info(self):
        """Test creating a host with all fields."""
        host = HostInfo(
            ip="192.168.1.1",
            mac="00:11:22:33:44:55",
            hostname="router.local",
            status=HostStatus.UP,
            vendor="Cisco",
            open_ports=[22, 80, 443],
            is_expected=True,
            is_new=False,
        )
        assert host.mac == "00:11:22:33:44:55"
        assert host.hostname == "router.local"
        assert host.vendor == "Cisco"
        assert 22 in host.open_ports

    def test_down_status(self):
        """Test host with DOWN status."""
        host = HostInfo(ip="192.168.1.2", status=HostStatus.DOWN)
        assert host.status == HostStatus.DOWN


class TestHostInfoDisplayName:
    """Tests for HostInfo display_name property."""

    def test_with_hostname(self):
        """Test display_name when hostname is available."""
        host = HostInfo(
            ip="192.168.1.1",
            hostname="router.local",
            vendor="Cisco",
        )
        assert host.display_name == "router.local"

    def test_with_vendor_no_hostname(self):
        """Test display_name when only vendor is available."""
        host = HostInfo(
            ip="192.168.1.1",
            vendor="Cisco",
        )
        assert host.display_name == "192.168.1.1 (Cisco)"

    def test_ip_only(self):
        """Test display_name when only IP is available."""
        host = HostInfo(ip="192.168.1.1")
        assert host.display_name == "192.168.1.1"


class TestScanResult:
    """Tests for ScanResult model."""

    def test_basic_creation(self):
        """Test creating a basic scan result."""
        result = ScanResult(
            target_name="Local Network",
            target_range="192.168.1.0/24",
        )
        assert result.target_name == "Local Network"
        assert result.target_range == "192.168.1.0/24"
        assert result.hosts == []
        assert result.duration_seconds == 0.0
        assert result.error is None

    def test_with_hosts(self):
        """Test scan result with discovered hosts."""
        hosts = [
            HostInfo(ip="192.168.1.1", status=HostStatus.UP),
            HostInfo(ip="192.168.1.2", status=HostStatus.UP),
            HostInfo(ip="192.168.1.3", status=HostStatus.DOWN),
        ]
        result = ScanResult(
            target_name="Local",
            target_range="192.168.1.0/24",
            hosts=hosts,
        )
        assert len(result.hosts) == 3

    def test_with_error(self):
        """Test scan result with error."""
        result = ScanResult(
            target_name="Local",
            target_range="192.168.1.0/24",
            error="Permission denied",
        )
        assert result.error == "Permission denied"


class TestScanResultProperties:
    """Tests for ScanResult computed properties."""

    @pytest.fixture
    def sample_result(self):
        """Create a sample scan result with various hosts."""
        hosts = [
            HostInfo(ip="192.168.1.1", status=HostStatus.UP),
            HostInfo(ip="192.168.1.2", status=HostStatus.UP),
            HostInfo(ip="192.168.1.3", status=HostStatus.DOWN),
            HostInfo(ip="192.168.1.4", status=HostStatus.UP, is_new=True),
            HostInfo(ip="192.168.1.5", status=HostStatus.UNKNOWN),
        ]
        return ScanResult(
            target_name="Local",
            target_range="192.168.1.0/24",
            hosts=hosts,
        )

    def test_hosts_up(self, sample_result):
        """Test hosts_up property counts UP hosts."""
        assert sample_result.hosts_up == 3

    def test_hosts_down(self, sample_result):
        """Test hosts_down property counts DOWN hosts."""
        assert sample_result.hosts_down == 1

    def test_new_hosts(self, sample_result):
        """Test new_hosts property returns only new hosts."""
        new_hosts = sample_result.new_hosts
        assert len(new_hosts) == 1
        assert new_hosts[0].ip == "192.168.1.4"

    def test_empty_result_properties(self):
        """Test properties on empty result."""
        result = ScanResult(
            target_name="Empty",
            target_range="192.168.1.0/24",
        )
        assert result.hosts_up == 0
        assert result.hosts_down == 0
        assert result.new_hosts == []
