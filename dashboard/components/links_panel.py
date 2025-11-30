"""Links panel component for displaying saved bookmarks."""

import logging
import re
import webbrowser
from urllib.parse import urlparse

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Label, ListItem, ListView, Static, TabbedContent, TabPane

from ..models.config import LinkCategory, LinkItem

logger = logging.getLogger(__name__)


def escape_markup(text: str) -> str:
    """Escape Rich markup characters in user content."""
    # Escape brackets which are used for Rich markup
    return text.replace("[", r"\[").replace("]", r"\]")


def sanitize_id(name: str) -> str:
    """Create a safe CSS ID from a name."""
    # Remove non-alphanumeric chars except hyphens, lowercase, replace spaces
    safe = re.sub(r"[^a-zA-Z0-9\s-]", "", name)
    return safe.lower().replace(" ", "-") or "unnamed"


class LinkListItem(ListItem):
    """A single link item in the list."""

    def __init__(self, item: LinkItem) -> None:
        super().__init__()
        self.link_item = item

    def compose(self) -> ComposeResult:
        name = escape_markup(self.link_item.name)
        desc = (
            f"\n[dim]{escape_markup(self.link_item.description)}[/dim]"
            if self.link_item.description
            else ""
        )
        yield Static(
            f"[bold]{name}[/bold]{desc}",
            markup=True,
        )


class LinksList(ListView):
    """List view for links with keyboard navigation."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select_cursor", "Open", show=True),
    ]

    class LinkSelected(Message):
        """Message sent when a link is selected."""

        def __init__(self, item: LinkItem) -> None:
            super().__init__()
            self.item = item

    def __init__(self, items: list[LinkItem] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._items = items or []

    def compose(self) -> ComposeResult:
        for item in self._items:
            yield LinkListItem(item)

    def update_items(self, items: list[LinkItem]) -> None:
        """Update the list with new items."""
        self._items = items
        self.clear()
        for item in items:
            self.append(LinkListItem(item))

    def action_select_cursor(self) -> None:
        """Handle item selection."""
        if self.highlighted_child and isinstance(self.highlighted_child, LinkListItem):
            self.post_message(self.LinkSelected(self.highlighted_child.link_item))


class CategoryTab(TabPane):
    """A tab containing links from a category."""

    def __init__(self, category: LinkCategory) -> None:
        super().__init__(category.name, id=f"link-tab-{sanitize_id(category.name)}")
        self.category = category

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            if not self.category.links:
                yield Label(
                    "[dim]No links in this category[/dim]\n\n"
                    "Press [bold]a[/bold] to add a new link",
                    id="links-empty",
                )
            else:
                yield LinksList(self.category.links, id=f"links-list-{self.category.name}")

    def update_links(self, links: list[LinkItem]) -> None:
        """Update links in this category."""
        self.category.links = links
        try:
            links_list = self.query_one(LinksList)
            links_list.update_items(links)
            self.query_one("#links-empty", Label).display = False
            links_list.display = True
        except Exception:
            pass


class LinksPanel(Static):
    """Panel for displaying saved links grouped by category."""

    DEFAULT_CSS = """
    LinksPanel {
        height: 1fr;
    }

    LinksPanel TabbedContent {
        height: 1fr;
    }

    LinksPanel TabPane {
        padding: 0 1;
        height: 1fr;
    }

    LinksPanel LinksList {
        height: 1fr;
    }

    LinksPanel ListItem {
        padding: 0 1;
    }

    LinksPanel ListItem:hover {
        background: $surface-lighten-1;
    }

    LinksPanel ListItem.-highlight {
        background: $primary-darken-2;
    }

    LinksPanel #links-empty {
        padding: 2;
        text-align: center;
        color: $text-muted;
    }

    LinksPanel #no-categories {
        padding: 2;
        text-align: center;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("a", "add_link", "Add Link", show=True),
    ]

    class AddLinkRequested(Message):
        """Message sent when user wants to add a new link."""

        pass

    def __init__(self, categories: list[LinkCategory] | None = None) -> None:
        super().__init__()
        self._categories = categories or []

    def compose(self) -> ComposeResult:
        if not self._categories:
            yield Label(
                "No link categories configured\n\n"
                "[dim]Press 'a' to add a link or 's' for Settings[/dim]",
                id="no-categories",
            )
        else:
            with TabbedContent():
                for category in self._categories:
                    yield CategoryTab(category)

    def action_add_link(self) -> None:
        """Request to add a new link."""
        self.post_message(self.AddLinkRequested())

    def update_categories(self, categories: list[LinkCategory]) -> None:
        """Update all categories."""
        self._categories = categories
        # Would need to rebuild UI for full update

    def on_links_list_link_selected(self, event: LinksList.LinkSelected) -> None:
        """Handle link selection - open in browser."""
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
