# Contributing to Daily Dashboard

Thank you for your interest in contributing to Daily Dashboard! This document provides guidelines and information for contributors.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- sudo/root access (for network scanning features)

### Setting Up the Development Environment

1. **Clone the repository**
   ```bash
   git clone https://github.com/dropup-studio/daily-dashboard.git
   cd daily-dashboard
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Set up pre-commit hooks**
   ```bash
   pre-commit install
   ```

5. **Copy the example config**
   ```bash
   cp config.example.json config.json
   ```

6. **Run the application**
   ```bash
   sudo python -m dashboard
   ```

## Development Workflow

### Code Style

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting. The configuration is in `pyproject.toml`.

- Run linter: `ruff check .`
- Run formatter: `ruff format .`
- Fix auto-fixable issues: `ruff check --fix .`

### Type Checking

We use [mypy](https://mypy.readthedocs.io/) for static type checking.

```bash
mypy dashboard
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=dashboard --cov-report=term-missing

# Run specific test file
pytest tests/test_models/test_config.py

# Run tests matching a pattern
pytest -k "test_valid"
```

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`. To run them manually:

```bash
pre-commit run --all-files
```

## Project Structure

```
daily-dashboard/
├── dashboard/              # Main package
│   ├── __init__.py        # Version and metadata
│   ├── __main__.py        # CLI entry point
│   ├── app.py             # Main Textual application
│   ├── components/        # UI widgets
│   ├── models/            # Pydantic data models
│   └── services/          # Business logic
├── tests/                 # Test suite
│   ├── test_models/       # Model tests
│   └── test_services/     # Service tests
├── config.example.json    # Example configuration
├── pyproject.toml         # Project metadata and tool config
└── README.md              # Project documentation
```

## Submitting Changes

### Pull Request Process

1. **Fork the repository** and create your branch from `main`

2. **Make your changes** following the code style guidelines

3. **Add tests** for any new functionality

4. **Update documentation** if needed

5. **Ensure all checks pass**
   ```bash
   ruff check .
   ruff format --check .
   mypy dashboard
   pytest
   ```

6. **Write a clear commit message** describing your changes

7. **Open a Pull Request** with a clear description of:
   - What changes were made
   - Why the changes were made
   - Any breaking changes
   - Related issues

### Commit Messages

We follow conventional commit messages:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

Example:
```
feat: add weather forecast panel

- Add WeatherPanel component with 5-day forecast
- Integrate Open-Meteo API for weather data
- Add location search functionality
```

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **Description** - Clear description of the bug
2. **Steps to reproduce** - Minimal steps to reproduce the issue
3. **Expected behavior** - What you expected to happen
4. **Actual behavior** - What actually happened
5. **Environment** - OS, Python version, terminal emulator
6. **Logs** - Relevant log output (run with `-v` flag)

### Feature Requests

Feature requests are welcome! Please include:

1. **Description** - Clear description of the feature
2. **Use case** - Why this feature would be useful
3. **Proposed implementation** - If you have ideas on how to implement it

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the technical merits of contributions
- Help others learn and grow

## License

By contributing to Daily Dashboard, you agree that your contributions will be licensed under the MIT License.

## Questions?

If you have questions, feel free to:

- Open an issue for discussion
- Check existing issues and pull requests

Thank you for contributing!
