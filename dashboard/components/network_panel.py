"""Network panel component for displaying scan results."""

import logging
import subprocess
import sys
import webbrowser

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import Button, DataTable, Label, Static

from ..models.scan_result import HostInfo, HostStatus, ScanResult
from ..services.network_info import NetworkInfo, SpeedTestResult

logger = logging.getLogger(__name__)


class NetworkPanel(Static):
    """Panel displaying network scan results."""

    class RefreshScanRequested(Message):
        """Message sent when user requests a network scan refresh."""

        pass

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("c", "copy_ip", "Copy IP", show=True),
        Binding("m", "copy_mac", "Copy MAC", show=True),
        Binding("o", "open_ip", "Open", show=True),
    ]

    DEFAULT_CSS = """
    NetworkPanel {
        height: 100%;
        border: solid $primary;
        padding: 0 1;
    }

    NetworkPanel #network-header {
        text-style: bold;
        color: $text;
        padding: 0 0 1 0;
    }

    NetworkPanel #network-status {
        color: $text-muted;
        padding: 0 0 1 0;
    }

    NetworkPanel #network-error {
        color: $error;
        padding: 1;
    }

    NetworkPanel #network-copy-status {
        color: $success;
        padding: 0 0 0 1;
    }

    NetworkPanel DataTable {
        height: 1fr;
    }

    NetworkPanel .host-up {
        color: $success;
    }

    NetworkPanel .host-down {
        color: $error;
    }

    NetworkPanel .host-new {
        color: $warning;
    }

    NetworkPanel #network-info-section {
        height: auto;
        padding: 1 0 0 0;
        border-top: solid $primary-darken-2;
    }

    NetworkPanel #network-buttons {
        height: auto;
        padding: 0 0 1 0;
    }

    NetworkPanel #network-buttons Button {
        margin-right: 1;
    }

    NetworkPanel #network-ips {
        height: auto;
    }

    NetworkPanel .ip-label {
        margin-right: 2;
    }

    NetworkPanel #speedtest-results {
        height: auto;
        padding: 1 0 0 0;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._loading = True
        self._result: ScanResult | None = None
        self._hosts: list[HostInfo] = []
        self._network_info = NetworkInfo()
        self._speedtest_running = False

    def compose(self) -> ComposeResult:
        yield Label("Network Scan", id="network-header")
        yield Label("", id="network-status")
        yield Label("", id="network-copy-status")
        yield Label("", id="network-error")
        yield Label("", id="network-empty")
        with VerticalScroll():
            yield DataTable(id="network-table")
        # Network info section below the table
        with Static(id="network-info-section"):
            with Horizontal(id="network-buttons"):
                yield Button("Speed Test", id="btn-speedtest", variant="primary")
                yield Button("Refresh Scan", id="btn-refresh", variant="default")
            with Horizontal(id="network-ips"):
                yield Label("Public: [dim]...[/dim]", id="public-ip", classes="ip-label")
                yield Label("Local: [dim]...[/dim]", id="local-ip", classes="ip-label")
                yield Label("Gateway: [dim]...[/dim]", id="gateway-ip", classes="ip-label")
                yield Label("DNS: [dim]...[/dim]", id="dns-servers", classes="ip-label")
            yield Label("", id="speedtest-results")

    def set_empty(self, message: str = "No network targets configured") -> None:
        """Display empty state message."""
        self._loading = False
        self.query_one("#network-status", Label).update("")
        self.query_one("#network-error", Label).update("")
        self.query_one("#network-empty", Label).update(
            f"[dim]{message}[/dim]\n[dim]Press 'n' to scan a network[/dim]"
        )

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Status", "IP Address", "Hostname", "MAC", "Vendor")
        table.cursor_type = "row"
        table.zebra_stripes = True
        # Load IP info on mount
        self.run_worker(self._load_ip_info(), exclusive=False)

    def set_loading(self, loading: bool, target_name: str = "") -> None:
        """Set loading state."""
        self._loading = loading
        status_label = self.query_one("#network-status", Label)
        self.query_one("#network-empty", Label).update("")  # Clear empty state
        self.query_one("#network-copy-status", Label).update("")  # Clear copy status

        if loading:
            status_label.update(f"Scanning {target_name}..." if target_name else "Scanning...")
        else:
            status_label.update("")

    def set_error(self, error: str) -> None:
        """Display an error message."""
        self._loading = False
        self.query_one("#network-empty", Label).update("")  # Clear empty state
        error_label = self.query_one("#network-error", Label)
        error_label.update(f"[red]{error}[/red]")
        self.query_one("#network-status", Label).update("")

    def update_results(self, result: ScanResult) -> None:
        """Update panel with scan results."""
        self._result = result
        self._loading = False

        self.query_one("#network-empty", Label).update("")  # Clear empty state
        self.query_one("#network-copy-status", Label).update("")  # Clear copy status
        error_label = self.query_one("#network-error", Label)
        status_label = self.query_one("#network-status", Label)
        table = self.query_one(DataTable)

        if result.error:
            error_label.update(f"[red]{result.error}[/red]")
            status_label.update("")
            return

        error_label.update("")

        # Update status summary
        up_count = result.hosts_up
        down_count = result.hosts_down
        new_count = len(result.new_hosts)

        status_parts = [f"[green]{up_count} up[/green]"]
        if down_count > 0:
            status_parts.append(f"[red]{down_count} down[/red]")
        if new_count > 0:
            status_parts.append(f"[yellow]{new_count} new[/yellow]")
        status_parts.append(f"[dim]({result.duration_seconds:.1f}s)[/dim]")

        status_label.update(" | ".join(status_parts))

        # Update table
        table.clear()
        self._hosts = []

        # Sort hosts by IP address numerically
        def ip_sort_key(host: HostInfo) -> tuple:
            """Sort by IP address numerically."""
            if host.ip:
                try:
                    parts = [int(p) for p in host.ip.split(".")]
                    return (0, parts)  # IPs first, sorted numerically
                except ValueError:
                    return (1, [host.ip])  # Invalid IPs after
            return (2, [host.hostname or ""])  # No IP last

        sorted_hosts = sorted(result.hosts, key=ip_sort_key)

        for host in sorted_hosts:
            self._hosts.append(host)
            status_icon = self._get_status_display(host)
            table.add_row(
                status_icon,
                host.ip or "-",
                host.hostname or "-",
                host.mac or "-",
                host.vendor or "-",
            )

    def _get_status_display(self, host: HostInfo) -> str:
        """Get status icon for a host."""
        if host.status == HostStatus.DOWN:
            return "[red]● DOWN[/red]"
        elif host.is_new:
            return "[yellow]● NEW[/yellow]"
        else:
            return "[green]● UP[/green]"

    def action_cursor_down(self) -> None:
        """Move cursor down in the table."""
        table = self.query_one(DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up in the table."""
        table = self.query_one(DataTable)
        table.action_cursor_up()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter key on DataTable row - open IP in browser."""
        row_index = event.cursor_row
        if row_index is None or row_index >= len(self._hosts):
            return

        host = self._hosts[row_index]
        if not host.ip:
            return

        self._open_ip_in_browser(host.ip)

    def action_copy_ip(self) -> None:
        """Copy the selected host's IP address to clipboard."""
        table = self.query_one(DataTable)
        cursor_row = table.cursor_row

        if cursor_row is None or cursor_row >= len(self._hosts):
            return

        host = self._hosts[cursor_row]
        if not host.ip:
            return

        if self._copy_to_clipboard(host.ip):
            self.query_one("#network-copy-status", Label).update(
                f"[green]Copied IP: {host.ip}[/green]"
            )
            self.set_timer(2, self._clear_copy_status)

    def action_copy_mac(self) -> None:
        """Copy the selected host's MAC address to clipboard."""
        table = self.query_one(DataTable)
        cursor_row = table.cursor_row

        if cursor_row is None or cursor_row >= len(self._hosts):
            return

        host = self._hosts[cursor_row]
        if not host.mac:
            self.query_one("#network-copy-status", Label).update("[yellow]No MAC address[/yellow]")
            self.set_timer(2, self._clear_copy_status)
            return

        if self._copy_to_clipboard(host.mac):
            self.query_one("#network-copy-status", Label).update(
                f"[green]Copied MAC: {host.mac}[/green]"
            )
            self.set_timer(2, self._clear_copy_status)

    def action_open_ip(self) -> None:
        """Open the selected host's IP address in browser."""
        table = self.query_one(DataTable)
        cursor_row = table.cursor_row

        if cursor_row is None or cursor_row >= len(self._hosts):
            return

        host = self._hosts[cursor_row]
        if not host.ip:
            return

        self._open_ip_in_browser(host.ip)

    def _open_ip_in_browser(self, ip: str) -> None:
        """Open an IP address in the browser."""
        url = f"http://{ip}"
        try:
            webbrowser.open(url)
            self.query_one("#network-copy-status", Label).update(f"[green]Opening: {url}[/green]")
            self.set_timer(2, self._clear_copy_status)
        except Exception as e:
            logger.error(f"Failed to open URL '{url}': {e}")
            self.query_one("#network-copy-status", Label).update(
                f"[red]Failed to open: {url}[/red]"
            )
            self.set_timer(2, self._clear_copy_status)

    def _clear_copy_status(self) -> None:
        """Clear the copy status message."""
        self.query_one("#network-copy-status", Label).update("")

    def _copy_to_clipboard(self, text: str) -> bool:
        """Copy text to system clipboard."""
        try:
            if sys.platform == "darwin":
                # macOS
                subprocess.run(
                    ["pbcopy"],
                    input=text.encode(),
                    check=True,
                    capture_output=True,
                )
                return True
            elif sys.platform == "linux":
                # Linux with xclip or xsel
                try:
                    subprocess.run(
                        ["xclip", "-selection", "clipboard"],
                        input=text.encode(),
                        check=True,
                        capture_output=True,
                    )
                    return True
                except FileNotFoundError:
                    subprocess.run(
                        ["xsel", "--clipboard", "--input"],
                        input=text.encode(),
                        check=True,
                        capture_output=True,
                    )
                    return True
            elif sys.platform == "win32":
                # Windows
                subprocess.run(
                    ["clip"],
                    input=text.encode(),
                    check=True,
                    capture_output=True,
                )
                return True
        except Exception:
            pass
        return False

    async def _load_ip_info(self) -> None:
        """Load public, local, gateway IP addresses, and DNS servers."""
        try:
            # Local, gateway, and DNS are sync, run them first
            local_ip = self._network_info.get_local_ip()
            gateway_ip = self._network_info.get_gateway_ip()
            dns_servers = self._network_info.get_dns_servers()

            if local_ip:
                self.query_one("#local-ip", Label).update(f"Local: [cyan]{local_ip}[/cyan]")
            else:
                self.query_one("#local-ip", Label).update("Local: [dim]unavailable[/dim]")

            if gateway_ip:
                self.query_one("#gateway-ip", Label).update(f"Gateway: [cyan]{gateway_ip}[/cyan]")
            else:
                self.query_one("#gateway-ip", Label).update("Gateway: [dim]unavailable[/dim]")

            if dns_servers:
                dns_str = ", ".join(dns_servers)
                self.query_one("#dns-servers", Label).update(f"DNS: [cyan]{dns_str}[/cyan]")
            else:
                self.query_one("#dns-servers", Label).update("DNS: [dim]unavailable[/dim]")

            # Public IP is async
            public_ip = await self._network_info.get_public_ip()
            if public_ip:
                self.query_one("#public-ip", Label).update(f"Public: [cyan]{public_ip}[/cyan]")
            else:
                self.query_one("#public-ip", Label).update("Public: [dim]unavailable[/dim]")

        except Exception as e:
            logger.error(f"Error loading IP info: {e}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-speedtest":
            if not self._speedtest_running:
                self.run_worker(self._run_speedtest(), exclusive=False)
        elif event.button.id == "btn-refresh":
            self.post_message(self.RefreshScanRequested())

    async def _run_speedtest(self) -> None:
        """Run speed test and display results."""
        if self._speedtest_running:
            return

        self._speedtest_running = True
        speedtest_btn = self.query_one("#btn-speedtest", Button)
        results_label = self.query_one("#speedtest-results", Label)

        # Update UI to show running state
        speedtest_btn.disabled = True
        speedtest_btn.label = "Testing..."
        results_label.update("[dim]Running speed test... (this may take 30-60 seconds)[/dim]")

        try:
            result = await self._network_info.run_speedtest()
            self._display_speedtest_result(result)
        except Exception as e:
            logger.error(f"Speed test error: {e}")
            results_label.update(f"[red]Error: {e}[/red]")
        finally:
            self._speedtest_running = False
            speedtest_btn.disabled = False
            speedtest_btn.label = "Speed Test"

    def _display_speedtest_result(self, result: SpeedTestResult) -> None:
        """Display speed test results."""
        results_label = self.query_one("#speedtest-results", Label)

        if not result.is_success:
            results_label.update(f"[red]{result.error}[/red]")
            return

        # Format results
        lines = [
            f"[green]↓[/green] Download: [bold]{result.download_mbps}[/bold] Mbps  "
            f"[cyan]↑[/cyan] Upload: [bold]{result.upload_mbps}[/bold] Mbps  "
            f"[yellow]⏱[/yellow] Ping: [bold]{result.ping_ms}[/bold] ms",
        ]

        if result.server_name or result.server_location:
            server_info = result.server_name
            if result.server_location:
                server_info = (
                    f"{server_info} ({result.server_location})"
                    if server_info
                    else result.server_location
                )
            lines.append(f"[dim]Server: {server_info}[/dim]")

        if result.isp:
            lines[0] += f"  [dim]ISP: {result.isp}[/dim]"

        results_label.update("\n".join(lines))

    def clear(self) -> None:
        """Clear all results."""
        self._result = None
        self._hosts = []
        self.query_one("#network-status", Label).update("")
        self.query_one("#network-error", Label).update("")
        self.query_one("#network-copy-status", Label).update("")
        self.query_one(DataTable).clear()
