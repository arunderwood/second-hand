# second-hand Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-01-17

## Active Technologies
- Python 3.14 (primary), matrix testing 3.13, 3.12 + FastAPI, uvicorn, htpy (type-safe HTML) (001-dashboard-init)
- N/A (static page, no persistence) (001-dashboard-init)
- Python 3.14 (primary), matrix testing 3.13, 3.12 + FastAPI, uvicorn, htpy (type-safe HTML), pychrony (from PyPI Test) (002-pychrony-integration)
- N/A (read-only queries to chronyd via socket) (002-pychrony-integration)

## Project Structure

```text
src/second_hand/
├── __init__.py
├── main.py
├── config.py
├── components/
│   ├── __init__.py
│   ├── base.py
│   ├── dashboard.py
│   ├── error.py
│   ├── rtc.py
│   ├── sources.py
│   ├── stats.py
│   └── tracking.py
├── services/
│   ├── __init__.py
│   └── chrony.py
└── utils/
    └── __init__.py
src/static/css/
tests/
```

## Commands

```bash
# Development
uv run uvicorn second_hand.main:app --reload

# Testing
uv run pytest
uv run pytest --cov=second_hand

# Type checking
uv run ty check src/

# Linting
uv run ruff check .
uv run ruff format .
```

## Pre-Commit Requirements

Run all quality checks before every git commit:

```bash
uv run ruff format .
uv run ruff check .
uv run ty check src/
uv run pytest
```

All checks must pass before committing.

## Code Style

Python 3.14: Follow standard conventions with full type hints. Use htpy for HTML generation.

## Recent Changes
- 002-pychrony-integration: Added Python 3.14 (primary), matrix testing 3.13, 3.12 + FastAPI, uvicorn, htpy (type-safe HTML), pychrony (from PyPI Test)
- 001-dashboard-init: Added Python 3.14 (primary), matrix testing 3.13, 3.12 + FastAPI, uvicorn, htpy (type-safe HTML)

<!-- MANUAL ADDITIONS START -->

## Testing Guidelines

### Unit Tests
- Unit tests MUST function without any reliance on a real chronyd server
- Mock all pychrony interactions using factory functions from `pychrony.testing`
- Use `@patch` decorators to mock `ChronyConnection` or `fetch_chrony_data`

### Integration Tests
- Integration tests MUST run against a real chronyd server when testing pychrony functionality
- If the connection to chronyd cannot be made, the tests MUST fail (not skip)
- Integration tests MUST be orchestrated against a dockerized version of chronyd to maximize portability of test execution
- Run integration tests via: `docker compose -f docker/docker-compose.test.yml run --rm test-integration`

<!-- MANUAL ADDITIONS END -->
