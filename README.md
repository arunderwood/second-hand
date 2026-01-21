<table><tr>
<td><img src="src/second_hand/static/img/logo.svg" alt="" width="48" height="48"></td>
<td><h1>second-hand</h1></td>
</tr></table>

A modern, type-safe dashboard for monitoring chrony time synchronization statistics.

## Overview

second-hand provides a clean, responsive web interface for viewing NTP/chrony time statistics on your homelab or server. Built with Python 3.14, FastAPI, and htpy for type-safe HTML generation.

**Current Status**: Dashboard initialization phase - displays placeholder content awaiting chrony integration.

## Quick Start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/arunderwood/second-hand.git
cd second-hand
uv sync --all-extras
uv run uvicorn second_hand.main:app --reload
```

Open http://localhost:8000

## Development

### Project Structure

```text
src/second_hand/
├── main.py          # FastAPI application
├── config.py        # Configuration management
└── components/      # htpy HTML components (type-safe!)
    ├── base.py      # Base layout
    └── dashboard.py # Dashboard page
src/static/css/      # Stylesheets
tests/               # Test suite
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=second_hand --cov-report=term-missing
```

### Type Checking

```bash
uv run ty check src/
```

### Linting

```bash
uv run ruff check .
uv run ruff format .
```

### Configuration

All settings are optional with sensible defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECOND_HAND_DEBUG` | `false` | Enable debug mode |
| `SECOND_HAND_HOST` | `127.0.0.1` | Server bind address |
| `SECOND_HAND_PORT` | `8000` | Server bind port |

## Technology Stack

- **Python 3.14** - Latest Python with performance improvements
- **FastAPI** - Modern async web framework
- **htpy** - Type-safe HTML generation
- **uvicorn** - Lightning-fast ASGI server
- **ty** - Fast type checker from Astral
- **ruff** - Fast linter and formatter from Astral

## License

MIT
