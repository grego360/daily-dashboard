"""Tests for NewsItem model."""

from datetime import UTC, datetime, timedelta

from dashboard.models.news_item import NewsItem


class TestNewsItem:
    """Tests for NewsItem model."""

    def test_basic_creation(self):
        """Test creating a basic news item."""
        item = NewsItem(
            title="Test Article",
            url="https://example.com/article",
            source="Test Source",
        )
        assert item.title == "Test Article"
        assert item.url == "https://example.com/article"
        assert item.source == "Test Source"
        assert item.published is None
        assert item.summary == ""

    def test_with_published_date(self):
        """Test creating an item with published date."""
        pub_date = datetime(2024, 1, 15, 12, 0, 0)
        item = NewsItem(
            title="Article",
            url="https://example.com",
            published=pub_date,
        )
        assert item.published == pub_date

    def test_with_summary(self):
        """Test creating an item with summary."""
        item = NewsItem(
            title="Article",
            url="https://example.com",
            summary="This is a test summary.",
        )
        assert item.summary == "This is a test summary."


class TestRelativeTime:
    """Tests for relative_time property."""

    def test_no_published_date(self):
        """Test relative_time returns empty string when no date."""
        item = NewsItem(title="Test", url="https://example.com")
        assert item.relative_time == ""

    def test_just_now_seconds(self):
        """Test relative_time for very recent items."""
        item = NewsItem(
            title="Test",
            url="https://example.com",
            published=datetime.now() - timedelta(seconds=30),
        )
        assert item.relative_time == "just now"

    def test_minutes_ago(self):
        """Test relative_time for items published minutes ago."""
        item = NewsItem(
            title="Test",
            url="https://example.com",
            published=datetime.now() - timedelta(minutes=5),
        )
        assert item.relative_time == "5m ago"

    def test_hours_ago(self):
        """Test relative_time for items published hours ago."""
        item = NewsItem(
            title="Test",
            url="https://example.com",
            published=datetime.now() - timedelta(hours=3),
        )
        assert item.relative_time == "3h ago"

    def test_days_ago(self):
        """Test relative_time for items published days ago."""
        item = NewsItem(
            title="Test",
            url="https://example.com",
            published=datetime.now() - timedelta(days=2),
        )
        assert item.relative_time == "2d ago"

    def test_weeks_ago(self):
        """Test relative_time for items published weeks ago."""
        item = NewsItem(
            title="Test",
            url="https://example.com",
            published=datetime.now() - timedelta(weeks=3),
        )
        assert item.relative_time == "3w ago"

    def test_future_date(self):
        """Test relative_time for future dates returns 'just now'."""
        item = NewsItem(
            title="Test",
            url="https://example.com",
            published=datetime.now() + timedelta(hours=1),
        )
        assert item.relative_time == "just now"

    def test_with_timezone(self):
        """Test relative_time with timezone-aware datetime."""
        now = datetime.now(UTC)
        item = NewsItem(
            title="Test",
            url="https://example.com",
            published=now - timedelta(hours=2),
        )
        assert item.relative_time == "2h ago"


class TestDisplayTitle:
    """Tests for display_title property."""

    def test_short_title_unchanged(self):
        """Test that short titles are unchanged."""
        item = NewsItem(
            title="Short Title",
            url="https://example.com",
        )
        assert item.display_title == "Short Title"

    def test_exactly_80_chars(self):
        """Test title exactly at limit is unchanged."""
        title = "x" * 80
        item = NewsItem(title=title, url="https://example.com")
        assert item.display_title == title
        assert len(item.display_title) == 80

    def test_long_title_truncated(self):
        """Test that long titles are truncated with ellipsis."""
        title = "x" * 100
        item = NewsItem(title=title, url="https://example.com")
        assert len(item.display_title) == 80
        assert item.display_title.endswith("...")

    def test_truncation_preserves_content(self):
        """Test that truncation keeps beginning of title."""
        title = "A" * 50 + "B" * 50
        item = NewsItem(title=title, url="https://example.com")
        assert item.display_title.startswith("A" * 50)
        assert item.display_title.endswith("...")
