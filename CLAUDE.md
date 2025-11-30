# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Daily Dashboard is a terminal-based dashboard (TUI) built with Python's Textual framework. It displays news feeds from RSS/JSON sources, weather information, saved links, and performs network scanning using scapy's ARP-based discovery. The app is designed as a daily glance tool with keyboard navigation.

## Installation

```bash
# From PyPI (recommended)
pip install daily-dashboard

# From Homebrew
brew tap grego360/tap
brew install daily-dashboard

# From source (development)
git clone https://github.com/grego360/daily-dashboard.git
cd daily-dashboard
pip install -e ".[dev]"
```

## Commands

```bash
# Run the dashboard (requires sudo for network scanning)
sudo daily-dashboard

# Run without sudo (network scanning disabled)
daily-dashboard

# Run with custom config file
daily-dashboard --config /path/to/config.json

# Run with verbose logging
daily-dashboard -v

# Show version
daily-dashboard --version

# Run as module (development)
sudo python -m dashboard

# Run tests
pytest

# Run linter
ruff check .

# Run type checker
mypy dashboard
```

Network scanning requires root privileges for raw socket access (ARP scanning).

## Architecture

### Package Structure
```
dashboard/
├── app.py              # Main Textual App class with modal screens
├── __main__.py         # CLI entry point, argument parsing, logging setup
├── components/         # Textual widgets (UI panels)
│   ├── news_panel.py   # News feeds with tabbed interface
│   ├── network_panel.py # Network scan results table
│   ├── weather_panel.py # Weather display
│   ├── links_panel.py  # Bookmarks by category
│   └── status_bar.py   # Bottom status bar
├── services/           # Data fetching and scanning logic
│   ├── feed_parser.py  # RSS/JSON feed parsing
│   ├── weather_service.py # Open-Meteo API client
│   ├── network_scanner.py # ARP-based scanning (scapy)
│   ├── known_hosts.py  # Device history persistence
│   ├── network_info.py # Local IP/public IP utilities
│   ├── nmap_scanner.py # Optional nmap integration
│   └── cache.py        # Response caching with TTL
└── models/             # Pydantic models for validation
    ├── config.py       # Configuration schema
    ├── news_item.py    # News item model
    ├── scan_result.py  # Network scan results
    └── weather.py      # Weather data model
```

### Key Components

**app.py** - `DashboardApp` class orchestrates the TUI:
- Composes layout with NewsPanel, WeatherPanel, NetworkPanel, LinksPanel, and StatusBar
- Uses Textual workers for async data loading (non-blocking UI)
- Modal screens: `HelpScreen`, `SettingsScreen`, `NetworkInputScreen`, `WeatherInputScreen`, `QuickAddFeedScreen`, `QuickAddLinkScreen`, `ConfigErrorScreen`
- Auto-refresh timer based on `refresh_interval_minutes` config
- Keyboard bindings: q (quit), r (refresh), s (settings), n (network scan), w (weather search), ? (help)

**components/** - Textual widgets:
- `NewsPanel`: Tabbed interface with `FeedTab` for each feed, empty state handling, `a` to add feed
- `NetworkPanel`: DataTable with j/k navigation, c (copy IP), m (copy MAC), o (open in browser)
- `WeatherPanel`: Current conditions and 5-day forecast display
- `LinksPanel`: Categorized bookmarks with `a` to add link
- `StatusBar`: Live clock, refresh status, next refresh countdown, activity indicator

**services/** - Business logic:
- `FeedParser`: Async HTTP with connection pooling, rate limiting (max 3 concurrent), detailed error handling
- `WeatherService`: Open-Meteo API client with geocoding support
- `NetworkScanner`: ARP scanning with configurable timeouts, MAC vendor lookup (40K+ vendors), mDNS hostname discovery (macOS)
- `KnownHostsStore`: Persists discovered devices to track new hosts across sessions
- `NmapScanner`: Optional advanced scanning if nmap is installed
- `Cache`: File-based cache with TTL, supports stale data retrieval

**models/** - Pydantic validation:
- `Config`: Main config with nested `FeedConfig`, `LinkCategory`, `NetworkConfig`, `WeatherConfig`, `Settings`
- `FeedConfig`: URL validation (http/https only), JSONPath validation
- `NetworkTarget`: CIDR range validation using `ipaddress` module
- `NetworkConfig`: Includes `dns_timeout_seconds` and `arp_timeout_seconds` for tuning
- `NewsItem`: Feed item with relative time formatting
- `ScanResult`/`HostInfo`: Scan results with status enum (UP/DOWN/UNKNOWN)
- `WeatherData`: Weather response with current conditions and forecast

### Data Flow
1. On mount, `DashboardApp._initial_load()` runs feeds, weather, and network scan in parallel
2. Feeds: Check cache → show stale data → fetch fresh (rate limited) → update cache
3. Weather: Fetch from Open-Meteo API using configured lat/lon
4. Network: Check privileges → ARP scan in thread pool → mDNS discovery → resolve hostnames → lookup MAC vendors → mark expected/new hosts → persist to known_hosts.json
5. Components update via `update_items()`/`update_results()`/`update_weather()` methods
6. Auto-refresh triggers based on `refresh_interval_minutes` setting

### Configuration
App reads `config.json` with structure:
- `feeds[]`: name, url (validated), type (rss/json), enabled, json_path (validated)
- `links[]`: categories with name and links array (name, url, description)
- `network`: scanner type, targets with CIDR ranges, expected hosts, `dns_timeout_seconds`, `arp_timeout_seconds`
- `weather`: enabled, location_name, latitude, longitude (default: London)
- `settings`: user_name, refresh_interval_minutes, cache_ttl_minutes, log_level

**Default configuration** (when no config.json exists):
- 3 example feeds: Hacker News, BBC News, TechCrunch
- Weather: London (51.5074, -0.1278)
- No network targets (requires user configuration)

### Privacy
These files contain personal data and are git-ignored:
- `config.json` - User settings (name, location, network ranges)
- `known_hosts.json` - Discovered network devices (MAC addresses)
- `.cache/` - Cached API responses

### Error Handling
- Config validation errors shown in modal dialog on startup
- Empty states shown when no feeds/targets configured
- Privilege check warns if running without sudo
- Feed errors categorized (timeout, connection, rate limit, HTTP errors)
- DNS resolution has configurable timeout (default 1.0s per host)

## Key Patterns

- Async operations use Textual's `run_worker()` with `exclusive=True` for data loading
- Heavy I/O (scapy scanning, DNS resolution) wrapped in `loop.run_in_executor()`
- Rate limiting via `asyncio.Semaphore` for feed requests
- Lazy loading for MAC vendor lookup (avoids blocking import)
- Components expose `set_loading()`, `set_error()`, `set_empty()`, and `update_*()` methods
- URLs sanitized before opening in browser (http/https only)
- Status colors: green=up, red=down, yellow=new host
- Settings are editable in-app via `s` key and saved to config.json

## Operations

### Logging
- Logs written to `logs/dashboard.log`
- Uses `RotatingFileHandler` (10MB max, 5 backups)
- Log level configurable via settings or `-v` flag

### Signal Handling
- SIGINT (Ctrl+C) and SIGTERM trigger graceful shutdown
- Cleans up network scanner and saves state before exit

### Release Process
1. Update version in `dashboard/__init__.py`
2. Update `CHANGELOG.md`
3. Commit and tag: `git tag v0.x.x`
4. Push with tags: `git push && git push --tags`
5. GitHub Actions automatically publishes to PyPI
6. Update Homebrew formula in `grego360/homebrew-tap`
