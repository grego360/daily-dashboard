"""Status bar component showing refresh status and keyboard hints."""

from datetime import datetime, timedelta

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Static


class StatusBar(Horizontal):
    """Bottom status bar with time, refresh info, and keyboard hints."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $surface-darken-1;
        color: $text-muted;
        padding: 0 1;
        width: 100%;
    }

    StatusBar #status-time {
        width: auto;
    }

    StatusBar #status-refresh {
        width: auto;
        padding-left: 2;
    }

    StatusBar #status-next-refresh {
        width: auto;
        padding-left: 2;
    }

    StatusBar #status-activity {
        width: auto;
        padding-left: 2;
        color: $warning;
    }

    StatusBar #status-spacer {
        width: 1fr;
    }

    StatusBar #status-hints {
        width: auto;
        text-align: right;
    }
    """

    last_refresh: reactive[datetime | None] = reactive(None)
    activity: reactive[str] = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self._last_refresh: datetime | None = None
        self._next_refresh: datetime | None = None
        self._auto_refresh_enabled: bool = False

    def compose(self) -> ComposeResult:
        yield Static("", id="status-time")
        yield Static("", id="status-refresh")
        yield Static("", id="status-next-refresh")
        yield Static("", id="status-activity")
        yield Static("", id="status-spacer")
        yield Static(
            "[dim]r[/dim] Refresh  [dim]s[/dim] Settings  [dim]q[/dim] Quit  [dim]?[/dim] Help",
            id="status-hints",
        )

    def on_mount(self) -> None:
        """Start clock update timer."""
        self.set_interval(1, self._update_time)

    def _update_time(self) -> None:
        """Update the current time display."""
        now = datetime.now()
        self.query_one("#status-time", Static).update(f"[bold]{now.strftime('%H:%M:%S')}[/bold]")

        # Update relative refresh time
        if self._last_refresh:
            delta = now - self._last_refresh
            minutes = int(delta.total_seconds() // 60)
            if minutes == 0:
                refresh_text = "Refreshed just now"
            elif minutes == 1:
                refresh_text = "Refreshed 1 min ago"
            else:
                refresh_text = f"Refreshed {minutes} mins ago"
            self.query_one("#status-refresh", Static).update(f"[dim]{refresh_text}[/dim]")

        # Update next refresh countdown
        if self._next_refresh and self._auto_refresh_enabled:
            delta = self._next_refresh - now
            if delta.total_seconds() > 0:
                minutes = int(delta.total_seconds() // 60)
                seconds = int(delta.total_seconds() % 60)
                if minutes > 0:
                    next_text = f"Next: {minutes}m {seconds}s"
                else:
                    next_text = f"Next: {seconds}s"
                self.query_one("#status-next-refresh", Static).update(f"[dim]{next_text}[/dim]")
            else:
                self.query_one("#status-next-refresh", Static).update("[dim]Refreshing...[/dim]")
        else:
            self.query_one("#status-next-refresh", Static).update("")

    def set_last_refresh(self, time: datetime | None = None) -> None:
        """Update the last refresh timestamp."""
        self._last_refresh = time or datetime.now()
        self._update_time()

    def set_next_refresh(self, time: datetime | None = None, interval_minutes: int = 0) -> None:
        """Set the next scheduled refresh time."""
        if interval_minutes > 0:
            self._next_refresh = datetime.now() + timedelta(minutes=interval_minutes)
            self._auto_refresh_enabled = True
        elif time:
            self._next_refresh = time
            self._auto_refresh_enabled = True
        else:
            self._next_refresh = None
            self._auto_refresh_enabled = False
        self._update_time()

    def set_activity(self, activity: str) -> None:
        """Set current activity message (e.g., 'Scanning...', 'Fetching feeds...')."""
        self.query_one("#status-activity", Static).update(
            f"[yellow]{activity}[/yellow]" if activity else ""
        )

    def clear_activity(self) -> None:
        """Clear activity message."""
        self.set_activity("")
