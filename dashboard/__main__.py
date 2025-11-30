"""Entry point for running the dashboard as a module."""

import argparse
import atexit
import logging
import signal
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .app import DashboardApp

# Global reference for signal handlers
_app: DashboardApp | None = None
_logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure logging with rotation support.

    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR)
    """
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]

    # Try to add rotating file handler
    log_dir = Path("logs")
    try:
        log_dir.mkdir(exist_ok=True)
        # Rotate at 10MB, keep 5 backup files
        file_handler = RotatingFileHandler(
            log_dir / "dashboard.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        handlers.append(file_handler)
    except (PermissionError, OSError):
        pass  # Skip file logging if we can't write

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


def _signal_handler(signum: int, frame: object) -> None:
    """Handle shutdown signals gracefully.

    Args:
        signum: Signal number received
        frame: Current stack frame (unused)
    """
    signal_name = signal.Signals(signum).name
    _logger.info(f"Received {signal_name}, shutting down gracefully...")

    if _app is not None:
        # Request the app to exit
        _app.exit()


def _cleanup() -> None:
    """Cleanup handler called on exit."""
    _logger.info("Daily Dashboard shutdown complete")


def setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""
    # Register signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Register cleanup on exit
    atexit.register(_cleanup)


def main() -> None:
    """Main entry point."""
    global _app

    parser = argparse.ArgumentParser(
        description="Daily Dashboard - A terminal-based dashboard for news, weather, and network scanning"
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.json"),
        help="Path to configuration file (default: config.json)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="store_true",
        help="Show version and exit",
    )

    args = parser.parse_args()

    # Handle version flag
    if args.version:
        from . import __version__

        print(f"Daily Dashboard v{__version__}")
        sys.exit(0)

    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)

    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()

    _logger.info("Starting Daily Dashboard")

    # Check if config exists
    if not args.config.exists():
        print(f"Config file not found: {args.config}")
        print("\nStarting with default configuration (example feeds included)...")
        print("Create a config.json file to customize. See config.example.json for format.")

    # Run the app
    _app = DashboardApp(config_path=args.config)
    _app.run()


if __name__ == "__main__":
    main()
