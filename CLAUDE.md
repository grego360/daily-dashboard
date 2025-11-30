# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Morning Dashboard is a terminal-based dashboard (TUI) built with Python's Textual framework. It displays news feeds from RSS/JSON sources and performs network scanning using scapy's ARP-based discovery. The app is designed as a morning glance tool with keyboard navigation.

## Commands

```bash
# Install dependencies (use virtual environment)
pip install -r requirements.txt

# Run the dashboard (requires sudo for network scanning)
sudo python -m dashboard

# Run with custom config file
sudo python -m dashboard --config /path/to/config.json

# Run with verbose logging
sudo python -m dashboard -v
```

Network scanning requires root privileges for raw socket access (ARP scanning).

## Architecture

### Package Structure
```
dashboard/
├── app.py              # Main Textual App class with modal screens
├── __main__.py         # CLI entry point, argument parsing, logging setup
├── components/         # Textual widgets (UI panels)
├── services/           # Data fetching and scanning logic
└── models/             # Pydantic models for validation
```

### Key Components

**app.py** - `DashboardApp` class orchestrates the TUI:
- Composes layout with NewsPanel, NetworkPanel, and StatusBar
- Uses Textual workers for async data loading (non-blocking UI)
- Modal screens: `HelpScreen`, `NetworkInputScreen`, `ConfigErrorScreen`
- Auto-refresh timer based on `refresh_interval_minutes` config
- Keyboard bindings for navigation and actions

**components/** - Textual widgets:
- `NewsPanel`: Tabbed interface with `FeedTab` for each feed, empty state handling
- `NetworkPanel`: DataTable with j/k navigation, copy IP to clipboard (c/Enter)
- `StatusBar`: Live clock, refresh status, next refresh countdown, activity indicator

**services/** - Business logic:
- `FeedParser`: Async HTTP with connection pooling, rate limiting (max 3 concurrent), detailed error handling
- `NetworkScanner`: ARP scanning with privilege check, DNS timeout (2s per host)
- `NmapScanner`: Optional advanced scanning if nmap is installed
- `Cache`: File-based cache with TTL, supports stale data retrieval

**models/** - Pydantic validation:
- `Config`: Main config with nested `FeedConfig`, `NetworkConfig`, `Settings`
- `FeedConfig`: URL validation (http/https only), JSONPath validation
- `NetworkTarget`: CIDR range validation using `ipaddress` module
- `NewsItem`: Feed item with relative time formatting
- `ScanResult`/`HostInfo`: Scan results with status enum (UP/DOWN/UNKNOWN)

### Data Flow
1. On mount, `DashboardApp._initial_load()` runs feeds and network scan in parallel
2. Feeds: Check cache → show stale data → fetch fresh (rate limited) → update cache
3. Network: Check privileges → ARP scan in thread pool → resolve hostnames (with timeout) → mark expected/new hosts
4. Components update via `update_items()`/`update_results()` methods
5. Auto-refresh triggers based on `refresh_interval_minutes` setting

### Configuration
App reads `config.json` with structure:
- `feeds[]`: name, url (validated), type (rss/json), enabled, json_path (validated)
- `network`: scanner type, targets with CIDR ranges (validated) and expected hosts
- `settings`: refresh_interval_minutes (enables auto-refresh), cache_ttl_minutes, log_level

### Error Handling
- Config validation errors shown in modal dialog on startup
- Empty states shown when no feeds/targets configured
- Privilege check warns if running without sudo
- Feed errors categorized (timeout, connection, rate limit, HTTP errors)
- DNS resolution has 2-second timeout per host

## Key Patterns

- Async operations use Textual's `run_worker()` with `exclusive=True` for data loading
- Heavy I/O (scapy scanning, DNS resolution) wrapped in `loop.run_in_executor()`
- Rate limiting via `asyncio.Semaphore` for feed requests
- Components expose `set_loading()`, `set_error()`, `set_empty()`, and `update_*()` methods
- URLs sanitized before opening in browser (http/https only)
- Status colors: green=up, red=down, yellow=new host
