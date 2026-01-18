# second-hand Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-01-17

## Active Technologies
- Python 3.14 (primary), matrix testing 3.13, 3.12 + FastAPI, uvicorn, htpy (type-safe HTML) (001-dashboard-init)
- N/A (static page, no persistence) (001-dashboard-init)

## Project Structure

```text
src/second_hand/
├── __init__.py
├── main.py
├── config.py
└── components/
    ├── __init__.py
    ├── base.py
    └── dashboard.py
src/static/css/
tests/
```

## Commands

```bash
# Development
uvicorn second_hand.main:app --reload

# Testing
pytest
pytest --cov=second_hand

# Type checking
ty check src/

# Linting
ruff check .
ruff format .
```

## Code Style

Python 3.14: Follow standard conventions with full type hints. Use htpy for HTML generation.

## Recent Changes
- 001-dashboard-init: Added Python 3.14 (primary), matrix testing 3.13, 3.12 + FastAPI, uvicorn, htpy (type-safe HTML)

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
