"""News panel component for displaying feed items."""

import logging
import webbrowser
from datetime import datetime
from urllib.parse import urlparse

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import (
    Label,
    ListItem,
    ListView,
    Static,
    TabbedContent,
    TabPane,
)

from ..models.config import LinkCategory
from ..models.news_item import NewsItem
from .links_panel import LinksPanel


def get_greeting(name: str = "") -> str:
    """Get time-appropriate greeting."""
    hour = datetime.now().hour
    if hour < 12:
        salute = "Good morning"
    elif hour < 17:
        salute = "Good afternoon"
    elif hour < 21:
        salute = "Good evening"
    else:
        salute = "Good night"

    name = name.strip() if name else ""
    if len(name) > 30:
        name = name[:30] + "…"

    if name:
        return f"{salute}, {name}!"
    return f"{salute}!"


logger = logging.getLogger(__name__)


class NewsListItem(ListItem):
    """A single news item in the list."""

    def __init__(self, item: NewsItem) -> None:
        super().__init__()
        self.news_item = item

    def compose(self) -> ComposeResult:
        time_str = self.news_item.relative_time
        yield Static(
            f"[bold]{self.news_item.display_title}[/bold]\n[dim]{time_str}[/dim]",
            markup=True,
        )


class NewsList(ListView):
    """List view for news items with keyboard navigation."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select_cursor", "Open", show=True),
    ]

    class ItemSelected(Message):
        """Message sent when a news item is selected."""

        def __init__(self, item: NewsItem) -> None:
            super().__init__()
            self.item = item

    def __init__(self, items: list[NewsItem] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._items = items or []

    def compose(self) -> ComposeResult:
        for item in self._items:
            yield NewsListItem(item)

    def update_items(self, items: list[NewsItem]) -> None:
        """Update the list with new items."""
        self._items = items
        self.clear()
        for item in items:
            self.append(NewsListItem(item))

    def action_select_cursor(self) -> None:
        """Handle item selection."""
        if self.highlighted_child and isinstance(self.highlighted_child, NewsListItem):
            self.post_message(self.ItemSelected(self.highlighted_child.news_item))


class FeedTab(TabPane):
    """Tab pane for a single feed (like CategoryTab in LinksPanel)."""

    def __init__(self, name: str, feed_id: str) -> None:
        super().__init__(name, id=f"feed-{feed_id}")
        self.feed_id = feed_id
        self._items: list[NewsItem] = []
        self._loading = True
        self._error: str | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("Loading...", id="loading-label")
            yield NewsList(id=f"list-{self.feed_id}")

    def on_mount(self) -> None:
        self.query_one(NewsList).display = False

    def set_loading(self, loading: bool) -> None:
        """Set loading state."""
        self._loading = loading
        loading_label = self.query_one("#loading-label", Label)
        news_list = self.query_one(NewsList)

        if loading:
            loading_label.update("Loading...")
            loading_label.display = True
            news_list.display = False
        else:
            loading_label.display = False
            news_list.display = True

    def set_error(self, error: str) -> None:
        """Display an error message."""
        self._error = error
        self._loading = False
        loading_label = self.query_one("#loading-label", Label)
        loading_label.update(f"[red]Error: {error}[/red]")
        loading_label.display = True
        self.query_one(NewsList).display = False

    def update_items(self, items: list[NewsItem]) -> None:
        """Update feed items."""
        self._items = items
        self._loading = False
        self._error = None
        self.set_loading(False)
        self.query_one(NewsList).update_items(items)


class NewsPane(TabPane):
    """News pane with feed tabs using TabbedContent (like LinksPanel)."""

    BINDINGS = [
        Binding("a", "add_feed", "Add Feed", show=True),
    ]

    class AddFeedRequested(Message):
        """Message sent when user wants to add a new feed."""

        pass

    def __init__(self, feeds: list[tuple[str, str]]) -> None:
        super().__init__("News", id="pane-news")
        self._feeds = feeds

    def compose(self) -> ComposeResult:
        if not self._feeds:
            yield Label(
                "No feeds configured\n\n[dim]Press 'a' to add a feed or 's' for Settings[/dim]",
                id="news-empty",
            )
        else:
            # Use TabbedContent like LinksPanel does (proven to work)
            with TabbedContent(id="feed-tabs"):
                for name, feed_id in self._feeds:
                    yield FeedTab(name, feed_id)

    def action_add_feed(self) -> None:
        """Request to add a new feed."""
        self.post_message(self.AddFeedRequested())

    def get_feed_content(self, feed_id: str) -> FeedTab | None:
        """Get feed tab by ID."""
        try:
            return self.query_one(f"#feed-{feed_id}", FeedTab)
        except Exception:
            return None


class LinksPane(TabPane):
    """Links pane containing the links panel."""

    def __init__(self, categories: list[LinkCategory]) -> None:
        super().__init__("Links", id="pane-links")
        self._categories = categories

    def compose(self) -> ComposeResult:
        yield LinksPanel(self._categories)


class NewsPanel(Static):
    """Main news panel with News/Links tabs."""

    DEFAULT_CSS = """
    NewsPanel {
        height: 100%;
        border: solid $primary;
    }

    NewsPanel #greeting {
        padding: 1 1 1 1;
        text-style: bold;
        color: $primary-lighten-2;
        height: auto;
        min-height: 3;
    }

    NewsPanel #main-tabs {
        height: 1fr;
    }

    NewsPanel #pane-news, NewsPanel #pane-links {
        height: 1fr;
        padding: 0;
    }

    NewsPanel #feed-tabs {
        height: 1fr;
    }

    NewsPanel FeedTab {
        height: 1fr;
        padding: 0 1;
    }

    NewsPanel FeedTab > VerticalScroll {
        height: 1fr;
    }

    NewsPanel NewsList {
        height: 1fr;
    }

    NewsPanel ListItem {
        padding: 0 1;
    }

    NewsPanel ListItem:hover {
        background: $surface-lighten-1;
    }

    NewsPanel ListItem.-highlight {
        background: $primary-darken-2;
    }

    NewsPanel #news-empty {
        padding: 2;
        text-align: center;
        color: $text-muted;
    }

    NewsPanel LinksPanel {
        height: 1fr;
    }
    """

    def __init__(
        self,
        feed_names: list[tuple[str, str]] | None = None,
        link_categories: list[LinkCategory] | None = None,
        user_name: str = "",
    ) -> None:
        """Initialize with feeds and link categories."""
        super().__init__()
        self._feeds = feed_names or []
        self._categories = link_categories or []
        self._user_name = user_name

    def compose(self) -> ComposeResult:
        yield Label(get_greeting(self._user_name), id="greeting")
        with TabbedContent(id="main-tabs"):
            yield NewsPane(self._feeds)
            yield LinksPane(self._categories)

    def update_greeting(self, user_name: str = "") -> None:
        """Update the greeting with a new name."""
        self._user_name = user_name
        try:
            self.query_one("#greeting", Label).update(get_greeting(user_name))
        except Exception:
            pass

    def get_feed_content(self, feed_id: str) -> FeedTab | None:
        """Get feed tab by ID."""
        try:
            return self.query_one(f"#feed-{feed_id}", FeedTab)
        except Exception:
            return None

    def get_links_panel(self) -> LinksPanel | None:
        """Get the links panel."""
        try:
            return self.query_one(LinksPanel)
        except Exception:
            return None

    def on_news_list_item_selected(self, event: NewsList.ItemSelected) -> None:
        """Handle news item selection - open in browser."""
        if not event.item.url:
            return

        try:
            parsed = urlparse(event.item.url)
            if parsed.scheme not in ("http", "https"):
                logger.warning(f"Rejecting non-HTTP URL: {event.item.url}")
                return
            if not parsed.netloc:
                logger.warning(f"Rejecting URL without host: {event.item.url}")
                return

            webbrowser.open(event.item.url)
        except Exception as e:
            logger.error(f"Failed to open URL '{event.item.url}': {e}")
