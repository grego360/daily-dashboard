# Changelog

All notable changes to Daily Dashboard will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.6] - 2024-11-30

### Changed

- Default weather location changed from Berlin to London
- Updated CLAUDE.md with installation, defaults, and operations docs

## [0.1.5] - 2024-11-30

### Changed

- Improved startup message when no config file exists

## [0.1.4] - 2024-11-30

### Added

- Default example feeds (Hacker News, BBC News, TechCrunch) for first-time users

## [0.1.3] - 2024-11-30

### Fixed

- StatusBar UnboundLocalError when widgets not mounted on startup

## [0.1.2] - 2024-11-30

### Fixed

- NewsPanel query race condition on startup with empty config
- WeatherPanel query race condition on startup with empty config
- NetworkPanel query race condition on startup with empty config

## [0.1.1] - 2024-11-30

### Fixed

- StatusBar query race condition on startup with empty config
- Renamed app title from "Morning Dashboard" to "Daily Dashboard"

## [0.1.0] - 2024-11-30

### Added

- Initial public release
- MIT License
- PyPI packaging with `pyproject.toml`
- GitHub Actions CI/CD pipeline
- Comprehensive test suite (84 tests)
- Pre-commit hooks configuration
- Type checking with mypy
- Code linting with Ruff
- Log rotation support (10MB, 5 backups)
- Graceful shutdown signal handling
- Version flag (`-V`, `--version`)
- Example configuration file
- Contributing guidelines

### Changed

- Renamed from "Morning Dashboard" to "Daily Dashboard"
- Updated logging to use RotatingFileHandler
- Improved documentation

## [0.1.0] - 2024-01-01

### Added

- Terminal-based dashboard using Textual framework
- News feed panel with RSS/JSON support
  - Tabbed interface for multiple feeds
  - Relative time display
  - Click to open in browser
- Network scanning panel
  - ARP-based device discovery using scapy
  - MAC vendor lookup
  - Hostname resolution
  - Expected vs new host detection
- Weather panel
  - Current conditions display
  - 5-day forecast
  - Location search
- Links panel
  - Bookmarks organized by category
  - Quick access to frequently used URLs
- Status bar
  - Live clock
  - Refresh countdown
  - Activity indicator
- Configuration system
  - JSON-based configuration
  - Pydantic validation
  - Hot reload via settings screen
- Keyboard navigation
  - `j/k` for list navigation
  - `c` to copy IP address
  - `r` to refresh
  - `s` for settings
  - `?` for help
- File-based caching with TTL
- Auto-refresh functionality
- Verbose logging mode

### Technical

- Async/await throughout for non-blocking UI
- Textual workers for background tasks
- Rate limiting for feed requests
- Graceful error handling and recovery

[Unreleased]: https://github.com/grego360/daily-dashboard/compare/v0.1.6...HEAD
[0.1.6]: https://github.com/grego360/daily-dashboard/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/grego360/daily-dashboard/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/grego360/daily-dashboard/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/grego360/daily-dashboard/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/grego360/daily-dashboard/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/grego360/daily-dashboard/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/grego360/daily-dashboard/releases/tag/v0.1.0
