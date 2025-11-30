"""News item data model."""

from datetime import datetime

from pydantic import BaseModel


class NewsItem(BaseModel):
    """Represents a single news article or feed item."""

    title: str
    url: str
    published: datetime | None = None
    source: str = ""
    summary: str = ""

    @property
    def relative_time(self) -> str:
        """Return human-readable relative time (e.g., '2 hours ago')."""
        if not self.published:
            return ""

        now = datetime.now(self.published.tzinfo) if self.published.tzinfo else datetime.now()
        delta = now - self.published

        seconds = delta.total_seconds()
        if seconds < 0:
            return "just now"

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours}h ago"
        elif seconds < 604800:
            days = int(seconds // 86400)
            return f"{days}d ago"
        else:
            weeks = int(seconds // 604800)
            return f"{weeks}w ago"

    @property
    def display_title(self) -> str:
        """Return title truncated to reasonable length."""
        max_len = 80
        if len(self.title) <= max_len:
            return self.title
        return self.title[: max_len - 3] + "..."
