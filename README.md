# Daily Dashboard

[![CI](https://github.com/dropup-studio/daily-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/dropup-studio/daily-dashboard/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/daily-dashboard.svg)](https://badge.fury.io/py/daily-dashboard)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A terminal-based dashboard (TUI) built with Python's Textual framework. Displays news feeds from RSS/JSON sources, weather information, saved links, and performs network scanning using scapy's ARP-based discovery.

![Daily Dashboard Screenshot](https://raw.githubusercontent.com/dropup-studio/daily-dashboard/main/docs/screenshot.png)

## Features

- **News Feeds**: RSS and JSON feed support with tabbed interface
- **Weather**: Current conditions and 5-day forecast via Open-Meteo API
- **Links**: Organized bookmarks by category
- **Network Scanner**: ARP-based device discovery on your local network
  - MAC vendor identification (40,000+ vendors)
  - mDNS hostname discovery (macOS)
  - Known hosts tracking (alerts for new devices)
  - Configurable scan timeouts
- **Keyboard Navigation**: Vim-style bindings (j/k) and standard arrows
- **Auto-refresh**: Configurable automatic data refresh
- **Caching**: Smart caching to reduce API calls
- **Settings UI**: In-app configuration (press `s`)

## Installation

### From PyPI (Recommended)

```bash
pip install daily-dashboard
```

### From Homebrew

```bash
brew tap dropup-studio/tap
brew install daily-dashboard
```

### From Source

```bash
git clone https://github.com/dropup-studio/daily-dashboard.git
cd daily-dashboard
pip install -e .
```

## Quick Start

1. **Create a configuration file**

   ```bash
   # Copy the example configuration
   curl -o config.json https://raw.githubusercontent.com/dropup-studio/daily-dashboard/main/config.example.json
   ```

2. **Edit the configuration** to add your feeds, location, and network targets

3. **Run the dashboard**

   ```bash
   # With network scanning (requires sudo)
   sudo daily-dashboard

   # Without network scanning
   daily-dashboard
   ```

## Configuration

Create a `config.json` file in your working directory:

```json
{
  "feeds": [
    {
      "name": "Hacker News",
      "url": "https://hnrss.org/frontpage",
      "type": "rss",
      "enabled": true
    }
  ],
  "links": [
    {
      "name": "Development",
      "links": [
        {
          "name": "GitHub",
          "url": "https://github.com",
          "description": "Code hosting"
        }
      ]
    }
  ],
  "network": {
    "scanner": "scapy",
    "targets": [
      {
        "name": "Home Network",
        "range": "192.168.1.0/24",
        "expected_hosts": []
      }
    ],
    "scan_interval_minutes": 15,
    "dns_timeout_seconds": 1.0,
    "arp_timeout_seconds": 3.0
  },
  "weather": {
    "enabled": true,
    "location_name": "London",
    "latitude": 51.5074,
    "longitude": -0.1278
  },
  "settings": {
    "user_name": "Your Name",
    "refresh_interval_minutes": 15,
    "cache_ttl_minutes": 5,
    "log_level": "INFO"
  }
}
```

See [config.example.json](config.example.json) for a complete example.

### Privacy Note

The following files contain personal data and are excluded from git:

| File | Contains |
|------|----------|
| `config.json` | Your name, location, network ranges |
| `known_hosts.json` | Discovered network devices (MAC addresses) |
| `.cache/` | Cached API responses |

When sharing your setup, use `config.example.json` as a template.

## Usage

```bash
# Run with default config (config.json in current directory)
daily-dashboard

# Run with sudo for network scanning
sudo daily-dashboard

# Run with custom config file
daily-dashboard --config /path/to/config.json

# Run with verbose logging
daily-dashboard -v

# Show version
daily-dashboard --version
```

### Running as a Module

```bash
python -m dashboard
```

## Keyboard Shortcuts

### Global

| Key | Action |
|-----|--------|
| `Tab` / `1-5` | Switch feed tabs |
| `j` / `k` or `Up` / `Down` | Navigate lists |
| `Enter` | Open selected item in browser |
| `r` | Refresh all data |
| `s` | Open settings |
| `n` | Quick network scan |
| `w` | Quick weather search |
| `?` | Show help |
| `q` | Quit |
| `Escape` | Close dialogs |

### Context-Specific

| Key | Context | Action |
|-----|---------|--------|
| `a` | News panel | Add new feed |
| `a` | Links panel | Add new link |
| `c` | Network panel | Copy IP address |
| `m` | Network panel | Copy MAC address |
| `o` | Network panel | Open IP in browser |

## Project Structure

```
daily-dashboard/
├── dashboard/
│   ├── __main__.py          # CLI entry point
│   ├── app.py               # Main Textual application
│   ├── components/          # UI widgets
│   │   ├── news_panel.py    # News feeds display
│   │   ├── network_panel.py # Network scan results
│   │   ├── weather_panel.py # Weather display
│   │   ├── links_panel.py   # Bookmarks panel
│   │   └── status_bar.py    # Bottom status bar
│   ├── models/              # Pydantic data models
│   │   ├── config.py        # Configuration schema
│   │   ├── news_item.py     # News item model
│   │   ├── scan_result.py   # Network scan results
│   │   └── weather.py       # Weather data model
│   └── services/            # Business logic
│       ├── feed_parser.py   # RSS/JSON feed parsing
│       ├── weather_service.py # Open-Meteo API client
│       ├── network_scanner.py # ARP-based scanning (scapy)
│       ├── known_hosts.py   # Device history persistence
│       └── cache.py         # Response caching
├── tests/                   # Test suite
├── .github/                 # CI/CD workflows
├── config.example.json      # Example configuration
├── pyproject.toml           # Project metadata
├── CONTRIBUTING.md          # Development guidelines
├── CHANGELOG.md             # Version history
└── README.md
```

## Troubleshooting

### Network scanning not working

- Ensure you're running with `sudo`
- On Linux, you can grant capabilities to avoid running as root:
  ```bash
  sudo setcap cap_net_raw,cap_net_admin=eip $(which python)
  ```

### Feed not loading

- Check the URL is accessible
- RSS feeds should return valid XML
- JSON feeds need a `json_path` configured to extract items

### Weather not showing

- Verify latitude/longitude are correct
- Use the `w` key to search for a location by name

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .

# Run type checker
mypy dashboard
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Costel Grigoras ([@dropup-studio](https://github.com/dropup-studio))

## Acknowledgments

- [Textual](https://textual.textualize.io/) - TUI framework
- [Open-Meteo](https://open-meteo.com/) - Free weather API
- [Scapy](https://scapy.net/) - Network packet manipulation
- [mac-vendor-lookup](https://github.com/bauerj/mac_vendor_lookup) - MAC address vendor database
