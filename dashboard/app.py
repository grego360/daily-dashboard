"""Main Textual application for Daily Dashboard."""

import asyncio
import json
import logging
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
    TabbedContent,
    TabPane,
)

from .components.links_panel import LinksPanel
from .components.network_panel import NetworkPanel
from .components.news_panel import NewsPane, NewsPanel
from .components.status_bar import StatusBar
from .components.weather_panel import WeatherPanel
from .models.config import Config
from .services.cache import Cache
from .services.feed_parser import FeedParser
from .services.known_hosts import KnownHostsStore
from .services.network_scanner import NetworkScanner
from .services.weather_service import WeatherService

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """Add scheme to URL if not present.

    - IP addresses and localhost → http://
    - Domain names → https://
    """
    if url.startswith(("http://", "https://")):
        return url

    # Extract host (before any port or path)
    host = url.split("/")[0].split(":")[0]

    # Use http for local addresses, https for domains
    if host == "localhost" or host.replace(".", "").isdigit():
        return f"http://{url}"
    return f"https://{url}"


class NetworkInputScreen(ModalScreen[str | None]):
    """Modal for entering network range to scan."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    NetworkInputScreen {
        align: center middle;
    }

    NetworkInputScreen > Vertical {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    NetworkInputScreen #network-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }

    NetworkInputScreen #network-hint {
        color: $text-muted;
        padding-bottom: 1;
    }

    NetworkInputScreen Input {
        margin-bottom: 1;
    }

    NetworkInputScreen #button-row {
        align: center middle;
        height: auto;
    }

    NetworkInputScreen Button {
        margin: 0 1;
    }
    """

    def __init__(self, current_range: str = ""):
        super().__init__()
        self.current_range = current_range

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Network Range", id="network-title")
            yield Label("Enter CIDR notation (e.g., 192.168.1.0/24)", id="network-hint")
            yield Input(
                value=self.current_range,
                placeholder="10.0.0.0/24",
                id="network-input",
            )
            with Horizontal(id="button-row"):
                yield Button("Scan", variant="primary", id="scan-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "scan-btn":
            value = self.query_one(Input).value.strip()
            if value:
                self.dismiss(value)
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value:
            self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class WeatherInputScreen(ModalScreen[str | None]):
    """Modal for entering weather location."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    WeatherInputScreen {
        align: center middle;
    }

    WeatherInputScreen > Vertical {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    WeatherInputScreen #weather-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }

    WeatherInputScreen #weather-hint {
        color: $text-muted;
        padding-bottom: 1;
    }

    WeatherInputScreen Input {
        margin-bottom: 1;
    }

    WeatherInputScreen #button-row {
        align: center middle;
        height: auto;
    }

    WeatherInputScreen Button {
        margin: 0 1;
    }
    """

    def __init__(self, current_location: str = ""):
        super().__init__()
        self.current_location = current_location

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Weather Location", id="weather-title")
            yield Label("Enter town name or postcode", id="weather-hint")
            yield Input(
                value=self.current_location,
                placeholder="London, UK",
                id="weather-input",
            )
            with Horizontal(id="button-row"):
                yield Button("Search", variant="primary", id="search-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search-btn":
            value = self.query_one(Input).value.strip()
            if value:
                self.dismiss(value)
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value:
            self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class HelpScreen(ModalScreen):
    """Help overlay showing keyboard shortcuts."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("?", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Container {
        width: 60;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    HelpScreen #help-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }

    HelpScreen .help-section {
        padding-top: 1;
    }

    HelpScreen .help-key {
        color: $primary;
    }
    """

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Keyboard Shortcuts", id="help-title")
            yield Static(
                "[bold]Navigation[/bold]\n"
                "  [cyan]Tab[/cyan] / [cyan]\u2190\u2192[/cyan]   Switch feed tabs\n"
                "  [cyan]\u2191\u2193[/cyan] / [cyan]j/k[/cyan]    Navigate lists\n"
                "  [cyan]1-9[/cyan]         Jump to tab\n"
                "  [cyan]Enter[/cyan]       Open in browser\n",
                classes="help-section",
            )
            yield Static(
                "[bold]Actions[/bold]\n"
                "  [cyan]r[/cyan]           Refresh all\n"
                "  [cyan]s[/cyan]           Settings\n"
                "  [cyan]n[/cyan]           Quick network scan\n"
                "  [cyan]w[/cyan]           Quick weather search\n"
                "  [cyan]?[/cyan]           Show this help\n"
                "  [cyan]q[/cyan]           Quit\n"
                "  [cyan]Escape[/cyan]      Close dialogs\n",
                classes="help-section",
            )


class ConfigErrorScreen(ModalScreen):
    """Modal showing configuration errors."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("enter", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    ConfigErrorScreen {
        align: center middle;
    }

    ConfigErrorScreen > Vertical {
        width: 70;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }

    ConfigErrorScreen #error-title {
        text-align: center;
        text-style: bold;
        color: $error;
        padding-bottom: 1;
    }

    ConfigErrorScreen #error-message {
        padding: 1;
        background: $surface-darken-1;
        margin-bottom: 1;
    }

    ConfigErrorScreen #error-hint {
        color: $text-muted;
        padding-bottom: 1;
    }

    ConfigErrorScreen Button {
        width: 100%;
    }
    """

    def __init__(self, error_message: str, config_path: str = ""):
        super().__init__()
        self.error_message = error_message
        self.config_path = config_path

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Configuration Error", id="error-title")
            yield Static(f"[red]{self.error_message}[/red]", id="error-message")
            if self.config_path:
                yield Label(
                    f"[dim]Config file: {self.config_path}[/dim]\n"
                    "[dim]Fix the error and restart, or continue with defaults.[/dim]",
                    id="error-hint",
                )
            yield Button("Continue with Defaults", variant="warning", id="continue-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


class QuickAddLinkScreen(ModalScreen[dict | None]):
    """Modal for quickly adding a new link."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    QuickAddLinkScreen {
        align: center middle;
    }

    QuickAddLinkScreen > Vertical {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    QuickAddLinkScreen #add-link-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }

    QuickAddLinkScreen Input {
        margin-bottom: 1;
    }

    QuickAddLinkScreen #category-select {
        height: 3;
        margin-bottom: 1;
    }

    QuickAddLinkScreen #button-row {
        align: center middle;
        height: auto;
    }

    QuickAddLinkScreen Button {
        margin: 0 1;
    }
    """

    def __init__(self, categories: list[str]):
        super().__init__()
        self.categories = categories

    def compose(self) -> ComposeResult:
        from textual.widgets import Select

        with Vertical():
            yield Label("Add New Link", id="add-link-title")
            yield Input(placeholder="Link name", id="quick-link-name")
            yield Input(placeholder="URL (https://...)", id="quick-link-url")
            yield Input(placeholder="Description (optional)", id="quick-link-desc")

            if self.categories:
                options = [(cat, cat) for cat in self.categories]
                yield Select(options, value=self.categories[0], id="category-select")
            else:
                yield Input(placeholder="New category name", id="quick-category-name")

            with Horizontal(id="button-row"):
                yield Button("Add", variant="primary", id="add-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#quick-link-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-btn":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("quick-link-name", "quick-link-url", "quick-link-desc"):
            self._submit()

    def _submit(self) -> None:
        name = self.query_one("#quick-link-name", Input).value.strip()
        url = self.query_one("#quick-link-url", Input).value.strip()
        desc = self.query_one("#quick-link-desc", Input).value.strip()

        if not name or not url:
            self.notify("Name and URL are required", severity="warning")
            return

        # Get category
        try:
            from textual.widgets import Select

            category = self.query_one("#category-select", Select).value
        except Exception:
            category = self.query_one("#quick-category-name", Input).value.strip()
            if not category:
                self.notify("Category name is required", severity="warning")
                return

        self.dismiss(
            {
                "name": name,
                "url": url,
                "description": desc,
                "category": category,
            }
        )

    def action_cancel(self) -> None:
        self.dismiss(None)


class QuickAddFeedScreen(ModalScreen[dict | None]):
    """Modal for quickly adding a new RSS feed."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    QuickAddFeedScreen {
        align: center middle;
    }

    QuickAddFeedScreen > Vertical {
        width: 70;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    QuickAddFeedScreen #add-feed-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }

    QuickAddFeedScreen Input {
        margin-bottom: 1;
    }

    QuickAddFeedScreen #button-row {
        align: center middle;
        height: auto;
    }

    QuickAddFeedScreen Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Add New Feed", id="add-feed-title")
            yield Input(placeholder="Feed name (e.g., Tech News)", id="quick-feed-name")
            yield Input(placeholder="RSS URL (https://...)", id="quick-feed-url")
            with Horizontal(id="button-row"):
                yield Button("Add", variant="primary", id="add-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#quick-feed-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-btn":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        name = self.query_one("#quick-feed-name", Input).value.strip()
        url = self.query_one("#quick-feed-url", Input).value.strip()

        if not name or not url:
            self.notify("Name and URL are required", severity="warning")
            return

        self.dismiss({"name": name, "url": url})

    def action_cancel(self) -> None:
        self.dismiss(None)


class SettingsScreen(ModalScreen[bool]):
    """Settings screen for configuring feeds, weather, and network."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }

    SettingsScreen > Vertical {
        width: 80;
        height: 30;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    SettingsScreen #settings-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }

    SettingsScreen TabbedContent {
        height: 1fr;
    }

    SettingsScreen .settings-section {
        padding: 1;
    }

    SettingsScreen .section-label {
        padding-bottom: 1;
    }

    SettingsScreen Input {
        margin-bottom: 1;
    }

    SettingsScreen ListView {
        height: 10;
        border: solid $primary-darken-2;
        margin-bottom: 1;
    }

    SettingsScreen .feed-item {
        padding: 0 1;
    }

    SettingsScreen #button-row {
        align: center middle;
        height: auto;
        padding-top: 1;
    }

    SettingsScreen #button-row Button {
        margin: 0 1;
    }

    SettingsScreen .input-row {
        height: auto;
        margin-bottom: 1;
    }

    SettingsScreen .input-row Input {
        width: 1fr;
    }

    SettingsScreen .input-row Button {
        width: auto;
        min-width: 8;
    }
    """

    def __init__(self, config: "Config", config_path: Path):
        super().__init__()
        self.config = config
        self.config_path = config_path
        self.feeds_changed = False
        self._selected_feed_index: int | None = None
        self._selected_category_index: int = 0
        self._selected_link_index: int | None = None
        # Track editing state (index being edited, or None)
        self._editing_feed_index: int | None = None
        self._editing_link_index: int | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("⚙ Settings", id="settings-title")

            with TabbedContent():
                with TabPane("General", id="general-tab"):
                    with Vertical(classes="settings-section"):
                        yield Label("[bold]Your Name[/bold]", classes="section-label")
                        yield Input(
                            value=self.config.settings.user_name,
                            placeholder="Enter your name",
                            id="user-name-input",
                        )
                        yield Label("[dim]Used for personalized greetings[/dim]")

                with TabPane("Feeds", id="feeds-tab"):
                    with VerticalScroll(classes="settings-section"):
                        yield Label(
                            "[bold]RSS Feeds[/bold] [dim](click to select)[/dim]",
                            classes="section-label",
                        )
                        yield ListView(id="feeds-list")
                        with Horizontal(classes="input-row"):
                            yield Button("Edit", variant="primary", id="edit-feed-btn")
                            yield Button("Delete", variant="error", id="delete-feed-btn")
                        yield Label("[bold]Add New Feed[/bold]", classes="section-label")
                        with Horizontal(classes="input-row"):
                            yield Input(placeholder="Feed name", id="feed-name-input")
                            yield Input(placeholder="Feed URL", id="feed-url-input")
                            yield Button("+", variant="success", id="add-feed-btn")

                with TabPane("Weather", id="weather-tab"):
                    with Vertical(classes="settings-section"):
                        yield Label("[bold]Weather Location[/bold]", classes="section-label")
                        yield Input(
                            value=self.config.weather.location_name,
                            placeholder="City name or postcode",
                            id="weather-location-input",
                        )
                        yield Label(
                            "[dim]Enter city name and click Search to update coordinates[/dim]"
                        )
                        with Horizontal(classes="input-row"):
                            yield Input(
                                value=str(self.config.weather.latitude),
                                placeholder="Latitude",
                                id="weather-lat-input",
                            )
                            yield Input(
                                value=str(self.config.weather.longitude),
                                placeholder="Longitude",
                                id="weather-lon-input",
                            )
                            yield Button("Search", variant="primary", id="geocode-btn")

                with TabPane("Network", id="network-tab"):
                    with Vertical(classes="settings-section"):
                        yield Label("[bold]Network Scan Target[/bold]", classes="section-label")
                        yield Input(
                            value=self.config.network.targets[0].name
                            if self.config.network.targets
                            else "Local Network",
                            placeholder="Network name",
                            id="network-name-input",
                        )
                        yield Input(
                            value=self.config.network.targets[0].range
                            if self.config.network.targets
                            else "",
                            placeholder="CIDR range (e.g., 192.168.1.0/24)",
                            id="network-range-input",
                        )
                        yield Label("[bold]Scan Timeouts[/bold]", classes="section-label")
                        with Horizontal(classes="input-row"):
                            yield Input(
                                value=str(self.config.network.dns_timeout_seconds),
                                placeholder="DNS timeout (seconds)",
                                id="dns-timeout-input",
                            )
                            yield Label(" DNS timeout (0.5-2.0s)", classes="section-label")
                        with Horizontal(classes="input-row"):
                            yield Input(
                                value=str(self.config.network.arp_timeout_seconds),
                                placeholder="ARP timeout (seconds)",
                                id="arp-timeout-input",
                            )
                            yield Label(" ARP timeout (1.0-5.0s)", classes="section-label")

                with TabPane("Links", id="links-tab"):
                    with VerticalScroll(classes="settings-section"):
                        yield Label(
                            "[bold]Link Categories[/bold] [dim](click to select)[/dim]",
                            classes="section-label",
                        )
                        yield ListView(id="categories-list")
                        with Horizontal(classes="input-row"):
                            yield Input(placeholder="New category name", id="category-name-input")
                            yield Button("+", variant="success", id="add-category-btn")
                            yield Button("Delete", variant="error", id="delete-category-btn")
                        yield Label(
                            "[bold]Links[/bold] [dim](click to select)[/dim]",
                            classes="section-label",
                        )
                        yield ListView(id="links-list")
                        with Horizontal(classes="input-row"):
                            yield Button("Edit", variant="primary", id="edit-link-btn")
                            yield Button("Delete", variant="error", id="delete-link-btn")
                        yield Label("[bold]Add New Link[/bold]", classes="section-label")
                        with Horizontal(classes="input-row"):
                            yield Input(placeholder="Link name", id="link-name-input")
                            yield Input(placeholder="URL", id="link-url-input")
                        with Horizontal(classes="input-row"):
                            yield Input(placeholder="Description (optional)", id="link-desc-input")
                            yield Button("+", variant="success", id="add-link-btn")

            with Horizontal(id="button-row"):
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        """Populate feeds and links lists on mount."""
        self._refresh_feeds_list()
        self._refresh_categories_list()
        self._refresh_links_list()

    def _refresh_feeds_list(self) -> None:
        """Refresh the feeds list display."""
        feeds_list = self.query_one("#feeds-list", ListView)
        feeds_list.clear()
        for i, feed in enumerate(self.config.feeds):
            status = "✓" if feed.enabled else "✗"
            marker = "▶" if i == self._selected_feed_index else " "
            feeds_list.append(
                ListItem(
                    Label(
                        f"[cyan]{marker}[/][{'green' if feed.enabled else 'red'}]{status}[/] {feed.name}: [dim]{feed.url}[/dim]"
                    ),
                    classes="feed-item",
                )
            )

    def _refresh_categories_list(self) -> None:
        """Refresh the categories list display."""
        categories_list = self.query_one("#categories-list", ListView)
        categories_list.clear()
        for i, category in enumerate(self.config.links):
            marker = "▶" if i == self._selected_category_index else " "
            categories_list.append(
                ListItem(
                    Label(
                        f"[cyan]{marker}[/] {category.name} [dim]({len(category.links)} links)[/dim]"
                    ),
                    classes="feed-item",
                )
            )

    def _refresh_links_list(self) -> None:
        """Refresh the links list for the selected category."""
        links_list = self.query_one("#links-list", ListView)
        links_list.clear()
        self._selected_link_index = None  # Reset when category changes

        if not self.config.links or self._selected_category_index >= len(self.config.links):
            return

        category = self.config.links[self._selected_category_index]
        for i, link in enumerate(category.links):
            marker = "▶" if i == self._selected_link_index else " "
            desc = f" - [dim]{link.description}[/dim]" if link.description else ""
            links_list.append(
                ListItem(
                    Label(f"[cyan]{marker}[/] {link.name}{desc}\n   [dim]{link.url}[/dim]"),
                    classes="feed-item",
                )
            )

    def _refresh_links_list_selection_only(self) -> None:
        """Update just the selection markers without rebuilding the list."""
        # Just rebuild the list - simpler and works
        links_list = self.query_one("#links-list", ListView)
        links_list.clear()

        if not self.config.links or self._selected_category_index >= len(self.config.links):
            return

        category = self.config.links[self._selected_category_index]
        for i, link in enumerate(category.links):
            marker = "▶" if i == self._selected_link_index else " "
            desc = f" - [dim]{link.description}[/dim]" if link.description else ""
            links_list.append(
                ListItem(
                    Label(f"[cyan]{marker}[/] {link.name}{desc}\n   [dim]{link.url}[/dim]"),
                    classes="feed-item",
                )
            )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle list selection - just select, don't delete."""
        # Get index from position in list (no IDs to avoid duplicates on refresh)
        try:
            children = list(event.list_view.children)
            index = children.index(event.item)
        except (ValueError, IndexError):
            return

        # Handle feeds selection
        if event.list_view.id == "feeds-list":
            if 0 <= index < len(self.config.feeds):
                self._selected_feed_index = index
                self._refresh_feeds_list()

        # Handle category selection
        elif event.list_view.id == "categories-list":
            if 0 <= index < len(self.config.links):
                self._selected_category_index = index
                self._refresh_categories_list()
                self._refresh_links_list()

        # Handle links selection
        elif event.list_view.id == "links-list":
            if self.config.links and self._selected_category_index < len(self.config.links):
                category = self.config.links[self._selected_category_index]
                if 0 <= index < len(category.links):
                    self._selected_link_index = index
                    self._refresh_links_list_selection_only()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(False)

        elif event.button.id == "save-btn":
            await self._save_config()
            self.dismiss(True)

        elif event.button.id == "add-feed-btn":
            await self._add_feed()

        elif event.button.id == "geocode-btn":
            await self._geocode_location()

        elif event.button.id == "add-category-btn":
            self._add_category()

        elif event.button.id == "add-link-btn":
            self._add_link()

        # Edit/Delete handlers for Feeds
        elif event.button.id == "edit-feed-btn":
            self._edit_feed()

        elif event.button.id == "delete-feed-btn":
            self._delete_feed()

        # Delete handler for Categories
        elif event.button.id == "delete-category-btn":
            self._delete_category()

        # Edit/Delete handlers for Links
        elif event.button.id == "edit-link-btn":
            self._edit_link()

        elif event.button.id == "delete-link-btn":
            self._delete_link()

    async def _add_feed(self) -> None:
        """Add or update a feed."""
        name_input = self.query_one("#feed-name-input", Input)
        url_input = self.query_one("#feed-url-input", Input)

        name = name_input.value.strip()
        url = url_input.value.strip()

        if not name or not url:
            # If editing and inputs cleared, cancel edit
            if self._editing_feed_index is not None:
                self._editing_feed_index = None
                self.notify("Edit cancelled")
            return

        url = normalize_url(url)

        from .models.config import FeedConfig

        try:
            new_feed = FeedConfig(name=name, url=url)

            if self._editing_feed_index is not None:
                # Update existing feed
                self.config.feeds[self._editing_feed_index] = new_feed
                self._editing_feed_index = None
                self.notify(f"Updated: {name}")
            else:
                # Add new feed
                self.config.feeds.append(new_feed)
                self.notify(f"Added: {name}")

            self._refresh_feeds_list()
            name_input.value = ""
            url_input.value = ""
            self.feeds_changed = True

        except Exception as e:
            # Escape brackets to prevent Rich markup parsing errors
            error_msg = str(e).replace("[", "\\[").replace("]", "\\]")
            self.notify(f"Invalid feed: {error_msg}", severity="error")

    def _add_category(self) -> None:
        """Add a new link category."""
        name_input = self.query_one("#category-name-input", Input)
        name = name_input.value.strip()

        if not name:
            return

        from .models.config import LinkCategory

        # Check if category already exists
        for cat in self.config.links:
            if cat.name.lower() == name.lower():
                self.notify(f"Category '{name}' already exists", severity="warning")
                return

        new_category = LinkCategory(name=name)
        self.config.links.append(new_category)
        self._selected_category_index = len(self.config.links) - 1
        self._refresh_categories_list()
        self._refresh_links_list()
        name_input.value = ""
        self.notify(f"Added category: {name}")

    def _add_link(self) -> None:
        """Add or update a link in the selected category."""
        if not self.config.links:
            self.notify("Create a category first", severity="warning")
            return

        name_input = self.query_one("#link-name-input", Input)
        url_input = self.query_one("#link-url-input", Input)
        desc_input = self.query_one("#link-desc-input", Input)

        name = name_input.value.strip()
        url = url_input.value.strip()
        description = desc_input.value.strip()

        if not name or not url:
            # If editing and inputs cleared, cancel edit
            if self._editing_link_index is not None:
                self._editing_link_index = None
                self.notify("Edit cancelled")
            else:
                self.notify("Name and URL are required", severity="warning")
            return

        url = normalize_url(url)

        from .models.config import LinkItem

        try:
            new_link = LinkItem(name=name, url=url, description=description)
            category = self.config.links[self._selected_category_index]

            if self._editing_link_index is not None:
                # Update existing link
                category.links[self._editing_link_index] = new_link
                self._editing_link_index = None
                self.notify(f"Updated: {name}")
            else:
                # Add new link
                category.links.append(new_link)
                self.notify(f"Added: {name}")

            self._refresh_links_list()
            self._refresh_categories_list()  # Update link count

            name_input.value = ""
            url_input.value = ""
            desc_input.value = ""

        except Exception as e:
            # Escape brackets to prevent Rich markup parsing errors
            error_msg = str(e).replace("[", "\\[").replace("]", "\\]")
            self.notify(f"Invalid link: {error_msg}", severity="error")

    def _edit_feed(self) -> None:
        """Edit selected feed by populating input fields."""
        if self._selected_feed_index is None:
            self.notify("Select a feed first", severity="warning")
            return

        if self._selected_feed_index >= len(self.config.feeds):
            return

        feed = self.config.feeds[self._selected_feed_index]
        name_input = self.query_one("#feed-name-input", Input)
        url_input = self.query_one("#feed-url-input", Input)

        name_input.value = feed.name
        url_input.value = feed.url

        # Track that we're editing this feed
        self._editing_feed_index = self._selected_feed_index
        self.notify("Edit and click + to update, or clear inputs to cancel")

    def _delete_feed(self) -> None:
        """Delete selected feed."""
        if self._selected_feed_index is None:
            self.notify("Select a feed first", severity="warning")
            return

        if self._selected_feed_index >= len(self.config.feeds):
            return

        feed_name = self.config.feeds[self._selected_feed_index].name
        del self.config.feeds[self._selected_feed_index]
        self._selected_feed_index = None
        self._refresh_feeds_list()
        self.feeds_changed = True
        self.notify(f"Deleted: {feed_name}")

    def _delete_category(self) -> None:
        """Delete selected category and all its links."""
        if not self.config.links:
            return

        if self._selected_category_index >= len(self.config.links):
            return

        category_name = self.config.links[self._selected_category_index].name
        del self.config.links[self._selected_category_index]

        # Adjust selected index
        if self._selected_category_index >= len(self.config.links):
            self._selected_category_index = max(0, len(self.config.links) - 1)

        self._refresh_categories_list()
        self._refresh_links_list()
        self.notify(f"Deleted category: {category_name}")

    def _edit_link(self) -> None:
        """Edit selected link by populating input fields."""
        if self._selected_link_index is None:
            self.notify("Select a link first", severity="warning")
            return

        if not self.config.links or self._selected_category_index >= len(self.config.links):
            return

        category = self.config.links[self._selected_category_index]
        if self._selected_link_index >= len(category.links):
            return

        link = category.links[self._selected_link_index]
        name_input = self.query_one("#link-name-input", Input)
        url_input = self.query_one("#link-url-input", Input)
        desc_input = self.query_one("#link-desc-input", Input)

        name_input.value = link.name
        url_input.value = link.url
        desc_input.value = link.description

        # Track that we're editing this link
        self._editing_link_index = self._selected_link_index
        self.notify("Edit and click + to update, or clear inputs to cancel")

    def _delete_link(self) -> None:
        """Delete selected link."""
        if self._selected_link_index is None:
            self.notify("Select a link first", severity="warning")
            return

        if not self.config.links or self._selected_category_index >= len(self.config.links):
            return

        category = self.config.links[self._selected_category_index]
        if self._selected_link_index >= len(category.links):
            return

        link_name = category.links[self._selected_link_index].name
        del category.links[self._selected_link_index]
        self._selected_link_index = None
        self._refresh_links_list()
        self._refresh_categories_list()
        self.notify(f"Deleted: {link_name}")

    async def _geocode_location(self) -> None:
        """Look up coordinates for the entered location."""
        location_input = self.query_one("#weather-location-input", Input)
        lat_input = self.query_one("#weather-lat-input", Input)
        lon_input = self.query_one("#weather-lon-input", Input)

        query = location_input.value.strip()
        if not query:
            return

        self.notify(f"Looking up {query}...")

        weather_service = WeatherService()
        result = await weather_service.geocode(query)

        if result:
            location_name, lat, lon = result
            location_input.value = location_name
            lat_input.value = str(lat)
            lon_input.value = str(lon)
            self.notify(f"Found: {location_name}")
        else:
            self.notify(f"Location not found: {query}", severity="error")

    async def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            # Update user name
            user_name = self.query_one("#user-name-input", Input).value.strip()
            self.config.settings.user_name = user_name

            # Update weather config with validation
            location_input = self.query_one("#weather-location-input", Input)
            lat_input = self.query_one("#weather-lat-input", Input)
            lon_input = self.query_one("#weather-lon-input", Input)

            try:
                lat = float(lat_input.value.strip())
                lon = float(lon_input.value.strip())
                if not (-90 <= lat <= 90):
                    self.notify("Latitude must be between -90 and 90", severity="error")
                    return
                if not (-180 <= lon <= 180):
                    self.notify("Longitude must be between -180 and 180", severity="error")
                    return
            except ValueError:
                self.notify("Invalid latitude/longitude values", severity="error")
                return

            self.config.weather.location_name = location_input.value.strip()
            self.config.weather.latitude = lat
            self.config.weather.longitude = lon

            # Update network config with validation
            network_name = self.query_one("#network-name-input", Input).value.strip()
            network_range = self.query_one("#network-range-input", Input).value.strip()

            import ipaddress

            from .models.config import NetworkTarget

            if network_range:
                try:
                    ipaddress.ip_network(network_range, strict=False)
                except ValueError:
                    self.notify(f"Invalid network range: {network_range}", severity="error")
                    return

                if self.config.network.targets:
                    self.config.network.targets[0].name = network_name
                    self.config.network.targets[0].range = network_range
                else:
                    self.config.network.targets = [
                        NetworkTarget(name=network_name, range=network_range)
                    ]

            # Update timeout settings
            dns_timeout_input = self.query_one("#dns-timeout-input", Input)
            arp_timeout_input = self.query_one("#arp-timeout-input", Input)

            try:
                dns_timeout = float(dns_timeout_input.value.strip())
                arp_timeout = float(arp_timeout_input.value.strip())
                if not (0.1 <= dns_timeout <= 10.0):
                    self.notify(
                        "DNS timeout must be between 0.1 and 10.0 seconds", severity="error"
                    )
                    return
                if not (0.5 <= arp_timeout <= 30.0):
                    self.notify(
                        "ARP timeout must be between 0.5 and 30.0 seconds", severity="error"
                    )
                    return
                self.config.network.dns_timeout_seconds = dns_timeout
                self.config.network.arp_timeout_seconds = arp_timeout
            except ValueError:
                self.notify("Invalid timeout values", severity="error")
                return

            # Write to file
            config_dict = self.config.model_dump(mode="json")
            with open(self.config_path, "w") as f:
                json.dump(config_dict, f, indent=2)

            self.notify("Settings saved!")

        except Exception as e:
            self.notify(f"Error saving: {e}", severity="error")

    def action_cancel(self) -> None:
        self.dismiss(False)


class DashboardApp(App):
    """Daily Dashboard TUI Application."""

    TITLE = "Daily Dashboard"
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 2;
        grid-rows: 1fr auto;
    }

    #main-content {
        column-span: 2;
    }

    #news-container {
        width: 2fr;
        height: 100%;
    }

    #right-sidebar {
        width: 1fr;
        height: 100%;
    }

    #status-container {
        column-span: 2;
        height: 1;
    }

    NewsPanel {
        height: 100%;
    }

    WeatherPanel {
        height: auto;
        max-height: 6;
    }

    NetworkPanel {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "settings", "Settings"),
        Binding("n", "network", "Network"),
        Binding("w", "weather", "Weather"),
        Binding("?", "help", "Help"),
        Binding("1", "tab_1", "Tab 1", show=False),
        Binding("2", "tab_2", "Tab 2", show=False),
        Binding("3", "tab_3", "Tab 3", show=False),
        Binding("4", "tab_4", "Tab 4", show=False),
        Binding("5", "tab_5", "Tab 5", show=False),
    ]

    def __init__(self, config_path: Path | str = "config.json"):
        super().__init__()
        self.config_path = Path(config_path)
        self.config: Config | None = None
        self.config_error: str | None = None  # Store config error for display
        self.cache: Cache | None = None
        self.feed_parser: FeedParser | None = None
        self.known_hosts_store: KnownHostsStore | None = None
        self.network_scanner: NetworkScanner | None = None
        self.weather_service: WeatherService | None = None
        self._feed_parser_client_active = False  # Track if HTTP client is active

    def compose(self) -> ComposeResult:
        yield Header()

        # Load config to get feed names
        try:
            self.config = Config.load(self.config_path)
        except FileNotFoundError:
            self.config = Config()
            self.config_error = f"Config file not found: {self.config_path}"
            logger.warning(self.config_error)
        except Exception as e:
            self.config = Config()
            # Extract useful error message from Pydantic validation errors
            error_str = str(e)
            if "validation error" in error_str.lower():
                # Simplify Pydantic error message
                self.config_error = f"Invalid config: {error_str}"
            else:
                self.config_error = f"Failed to load config: {error_str}"
            logger.error(self.config_error)

        # Initialize services
        self.cache = Cache(ttl_minutes=self.config.settings.cache_ttl_minutes)
        self.feed_parser = FeedParser()
        # Known hosts store persists discovered devices alongside config
        known_hosts_path = self.config_path.parent / "known_hosts.json"
        self.known_hosts_store = KnownHostsStore(path=known_hosts_path)
        self.network_scanner = NetworkScanner(
            arp_timeout=self.config.network.arp_timeout_seconds,
            dns_timeout=self.config.network.dns_timeout_seconds,
            known_hosts_store=self.known_hosts_store,
        )
        self.weather_service = WeatherService()

        # Build feed tabs
        feed_tabs = [
            (feed.name, feed.name.lower().replace(" ", "-"))
            for feed in self.config.feeds
            if feed.enabled
        ]

        user_name = self.config.settings.user_name
        link_categories = self.config.links

        with Horizontal(id="main-content"):
            with Container(id="news-container"):
                yield NewsPanel(feed_tabs, link_categories=link_categories, user_name=user_name)
            with Vertical(id="right-sidebar"):
                yield WeatherPanel()
                yield NetworkPanel()

        with Container(id="status-container"):
            yield StatusBar()

    async def on_mount(self) -> None:
        """Start loading data when app mounts."""
        # Show config error modal if there was an error loading config
        if self.config_error:
            self.push_screen(ConfigErrorScreen(self.config_error, str(self.config_path)))

        # Initialize FeedParser HTTP client for connection pooling
        if self.feed_parser:
            await self.feed_parser.__aenter__()
            self._feed_parser_client_active = True

        self.run_worker(self._initial_load(), exclusive=True)

        # Set up auto-refresh timer if configured
        if self.config and self.config.settings.refresh_interval_minutes > 0:
            interval_seconds = self.config.settings.refresh_interval_minutes * 60
            self.set_interval(interval_seconds, self._auto_refresh)

    async def on_unmount(self) -> None:
        """Clean up resources when app unmounts."""
        # Close FeedParser HTTP client
        if self.feed_parser and self._feed_parser_client_active:
            await self.feed_parser.__aexit__(None, None, None)
            self._feed_parser_client_active = False

    def _auto_refresh(self) -> None:
        """Trigger automatic refresh."""
        self.run_worker(self._initial_load(), exclusive=True)

    async def _initial_load(self) -> None:
        """Load all data on startup."""
        status_bar = None
        try:
            status_bar = self.query_one(StatusBar)
            status_bar.set_activity("Loading...")
        except Exception:
            # StatusBar may not be mounted yet on first load
            pass

        # Load feeds, weather, and scan network in parallel
        await asyncio.gather(
            self._load_all_feeds(),
            self._load_weather(),
            self._run_network_scan(),
        )

        if status_bar:
            status_bar.set_last_refresh()
            status_bar.clear_activity()

            # Update next refresh countdown if auto-refresh is enabled
            if self.config and self.config.settings.refresh_interval_minutes > 0:
                status_bar.set_next_refresh(
                    interval_minutes=self.config.settings.refresh_interval_minutes
                )

    async def _load_all_feeds(self) -> None:
        """Load all configured feeds."""
        if not self.config or not self.feed_parser:
            return

        try:
            news_panel = self.query_one(NewsPanel)
        except Exception:
            # NewsPanel may not be mounted yet on first load
            return

        for feed_config in self.config.feeds:
            if not feed_config.enabled:
                continue

            feed_id = feed_config.name.lower().replace(" ", "-")
            feed_content = news_panel.get_feed_content(feed_id)

            if not feed_content:
                continue

            feed_content.set_loading(True)

            try:
                # Check cache first
                cache_key = f"feed_{feed_id}"
                cached = self.cache.get_stale(cache_key) if self.cache else None

                if cached:
                    from .models.news_item import NewsItem

                    items = [NewsItem.model_validate(i) for i in cached]
                    feed_content.update_items(items)

                # Fetch fresh data
                items = await self.feed_parser.fetch_feed(feed_config)

                if items:
                    feed_content.update_items(items)
                    if self.cache:
                        self.cache.set(cache_key, [i.model_dump(mode="json") for i in items])
                elif not cached:
                    feed_content.set_error("No items found")

            except Exception as e:
                logger.error(f"Error loading feed {feed_config.name}: {e}")
                feed_content.set_error(str(e))

    async def _load_weather(self) -> None:
        """Load weather data."""
        if not self.config or not self.weather_service:
            return

        try:
            weather_panel = self.query_one(WeatherPanel)
        except Exception:
            # WeatherPanel may not be mounted yet on first load
            return

        if not self.config.weather.enabled:
            weather_panel.set_empty("Weather disabled")
            return

        weather_panel.set_loading(True)

        try:
            # Check cache first
            cache_key = "weather"
            cached = self.cache.get_stale(cache_key) if self.cache else None

            if cached:
                from .models.weather import WeatherData

                weather_data = WeatherData.model_validate(cached)
                weather_panel.update_weather(weather_data)

            # Fetch fresh data
            weather_data = await self.weather_service.fetch_weather(self.config.weather)
            weather_panel.update_weather(weather_data)

            if self.cache and not weather_data.error:
                self.cache.set(cache_key, weather_data.model_dump(mode="json"))

        except Exception as e:
            logger.error(f"Error loading weather: {e}")
            weather_panel.set_error(str(e))

    async def _run_network_scan(self) -> None:
        """Run network scan for all configured targets."""
        if not self.config or not self.network_scanner:
            return

        try:
            network_panel = self.query_one(NetworkPanel)
        except Exception:
            # NetworkPanel may not be mounted yet on first load
            return

        # Check for scanner availability
        status_message = self.network_scanner.get_status_message()
        if status_message:
            network_panel.set_empty(status_message)
            return

        if not self.config.network.targets:
            network_panel.set_empty("No network targets configured")
            return

        for target in self.config.network.targets:
            network_panel.set_loading(True, target.name)

            try:
                result = await self.network_scanner.scan(target)
                network_panel.update_results(result)

                # Save known hosts after successful scan
                if self.known_hosts_store and not result.error:
                    self.known_hosts_store.save()

            except Exception as e:
                logger.error(f"Network scan error: {e}")
                network_panel.set_error(str(e))

    def action_refresh(self) -> None:
        """Refresh all data."""
        self.run_worker(self._initial_load(), exclusive=True)

    def action_help(self) -> None:
        """Show help screen."""
        self.push_screen(HelpScreen())

    def action_settings(self) -> None:
        """Show settings screen."""
        if not self.config:
            return

        def handle_settings_result(saved: bool) -> None:
            if saved:
                # Reload config and refresh
                self.run_worker(self._reload_after_settings(), exclusive=True)

        self.push_screen(
            SettingsScreen(self.config, self.config_path),
            handle_settings_result,
        )

    def on_links_panel_add_link_requested(self, event: LinksPanel.AddLinkRequested) -> None:
        """Handle quick-add link request from LinksPanel."""
        if not self.config:
            return

        categories = [cat.name for cat in self.config.links]

        def handle_add_link(result: dict | None) -> None:
            if result:
                self.run_worker(self._save_quick_link(result), exclusive=True)

        self.push_screen(QuickAddLinkScreen(categories), handle_add_link)

    def on_news_pane_add_feed_requested(self, event: NewsPane.AddFeedRequested) -> None:
        """Handle quick-add feed request from NewsPane."""
        if not self.config:
            return

        def handle_add_feed(result: dict | None) -> None:
            if result:
                self.run_worker(self._save_quick_feed(result), exclusive=True)

        self.push_screen(QuickAddFeedScreen(), handle_add_feed)

    def on_network_panel_refresh_scan_requested(
        self, event: NetworkPanel.RefreshScanRequested
    ) -> None:
        """Handle refresh scan request from NetworkPanel."""
        self.run_worker(self._run_network_scan(), exclusive=True)

    async def _save_quick_feed(self, feed_data: dict) -> None:
        """Save a quickly-added feed to config."""
        if not self.config:
            return

        from .models.config import FeedConfig

        try:
            new_feed = FeedConfig(
                name=feed_data["name"],
                url=normalize_url(feed_data["url"]),
            )
            self.config.feeds.append(new_feed)

            # Save config
            config_dict = self.config.model_dump(mode="json")
            with open(self.config_path, "w") as f:
                json.dump(config_dict, f, indent=2)

            self.notify(f"Added feed: {feed_data['name']}")

            # Reload app to show new feed
            await self._reload_after_settings()

        except Exception as e:
            self.notify(f"Error adding feed: {e}", severity="error")

    async def _save_quick_link(self, link_data: dict) -> None:
        """Save a quickly-added link to config."""
        if not self.config:
            return

        from .models.config import LinkCategory, LinkItem

        category_name = link_data["category"]

        # Find or create category (case-insensitive match)
        category = None
        for cat in self.config.links:
            if cat.name.lower() == category_name.lower():
                category = cat
                break

        if not category:
            category = LinkCategory(name=category_name)
            self.config.links.append(category)

        # Add the link
        try:
            new_link = LinkItem(
                name=link_data["name"],
                url=normalize_url(link_data["url"]),
                description=link_data.get("description", ""),
            )
            category.links.append(new_link)

            # Save config
            config_dict = self.config.model_dump(mode="json")
            with open(self.config_path, "w") as f:
                json.dump(config_dict, f, indent=2)

            self.notify(f"Added link: {link_data['name']}")

            # Reload app to show new link
            await self._reload_after_settings()

        except Exception as e:
            self.notify(f"Error adding link: {e}", severity="error")

    async def _reload_after_settings(self) -> None:
        """Reload config and refresh data after settings change."""
        try:
            self.config = Config.load(self.config_path)

            # Rebuild NewsPanel to reflect feed/link changes
            old_panel = self.query_one(NewsPanel)
            container = self.query_one("#news-container")

            # Build new feed tabs
            feed_tabs = [
                (feed.name, feed.name.lower().replace(" ", "-"))
                for feed in self.config.feeds
                if feed.enabled
            ]

            # Create new panel with updated data
            new_panel = NewsPanel(
                feed_tabs,
                link_categories=self.config.links,
                user_name=self.config.settings.user_name,
            )

            # Replace old with new
            await old_panel.remove()
            await container.mount(new_panel)

        except Exception as e:
            logger.error(f"Error reloading config: {e}")

        await self._initial_load()

    def action_network(self) -> None:
        """Show network input dialog."""
        current_range = ""
        if self.config and self.config.network.targets:
            current_range = self.config.network.targets[0].range

        def handle_network_input(new_range: str | None) -> None:
            if new_range:
                self.run_worker(self._scan_network(new_range), exclusive=True)

        self.push_screen(NetworkInputScreen(current_range), handle_network_input)

    async def _scan_network(self, network_range: str) -> None:
        """Scan a specific network range."""
        if not self.network_scanner:
            return

        from .models.config import NetworkTarget

        network_panel = self.query_one(NetworkPanel)
        status_bar = self.query_one(StatusBar)

        target = NetworkTarget(name="Custom Scan", range=network_range)

        network_panel.set_loading(True, network_range)
        status_bar.set_activity(f"Scanning {network_range}...")

        try:
            result = await self.network_scanner.scan(target)
            network_panel.update_results(result)

            # Save known hosts after successful scan
            if self.known_hosts_store and not result.error:
                self.known_hosts_store.save()
        except Exception as e:
            logger.error(f"Network scan error: {e}")
            network_panel.set_error(str(e))

        status_bar.set_last_refresh()
        status_bar.clear_activity()

    def action_weather(self) -> None:
        """Show weather location input dialog."""
        current_location = ""
        if self.config:
            current_location = self.config.weather.location_name

        def handle_weather_input(query: str | None) -> None:
            if query:
                self.run_worker(self._fetch_weather_for_location(query), exclusive=True)

        self.push_screen(WeatherInputScreen(current_location), handle_weather_input)

    async def _fetch_weather_for_location(self, query: str) -> None:
        """Fetch weather for a new location by name/postcode."""
        if not self.weather_service:
            return

        weather_panel = self.query_one(WeatherPanel)
        status_bar = self.query_one(StatusBar)

        weather_panel.set_loading(True)
        status_bar.set_activity(f"Looking up {query}...")

        try:
            # Geocode the location
            result = await self.weather_service.geocode(query)

            if not result:
                weather_panel.set_error(f"Location not found: {query}")
                status_bar.clear_activity()
                return

            location_name, lat, lon = result
            status_bar.set_activity(f"Fetching weather for {location_name}...")

            # Create a temporary config for this location
            from .models.config import WeatherConfig

            temp_config = WeatherConfig(
                enabled=True,
                location_name=location_name,
                latitude=lat,
                longitude=lon,
            )

            # Fetch weather
            weather_data = await self.weather_service.fetch_weather(temp_config)
            weather_panel.update_weather(weather_data)

            # Cache the result
            if self.cache and not weather_data.error:
                self.cache.set("weather", weather_data.model_dump(mode="json"))

        except Exception as e:
            logger.error(f"Error fetching weather for {query}: {e}")
            weather_panel.set_error(str(e))

        status_bar.clear_activity()

    def action_tab_1(self) -> None:
        self._switch_to_tab(0)

    def action_tab_2(self) -> None:
        self._switch_to_tab(1)

    def action_tab_3(self) -> None:
        self._switch_to_tab(2)

    def action_tab_4(self) -> None:
        self._switch_to_tab(3)

    def action_tab_5(self) -> None:
        self._switch_to_tab(4)

    def _switch_to_tab(self, index: int) -> None:
        """Switch to tab by index (within the feeds tabs)."""
        try:
            # Target the feeds TabbedContent (inside the News pane)
            feed_tabs = self.query_one("#feed-tabs", TabbedContent)
            tabs = list(feed_tabs.query(TabPane))
            if 0 <= index < len(tabs):
                feed_tabs.active = tabs[index].id or ""
        except Exception:
            pass
