# Quickstart: Dashboard Initialization

**Feature**: 001-dashboard-init
**Date**: 2026-01-17
**Updated**: 2026-01-17 (Modern stack)

## Prerequisites

- Python 3.14 (or 3.13/3.12 for compatibility testing)
- uv (recommended) or pip
- Git

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/arunderwood/second-hand.git
cd second-hand
```

### 2. Create virtual environment (using uv - recommended)

```bash
uv venv --python 3.14
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

Or with standard Python:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
uv pip install -e ".[dev]"
```

Or with pip:

```bash
pip install -e ".[dev]"
```

### 4. Install development tools

```bash
uv tool install ty@latest  # Astral's fast type checker
uv tool install ruff       # Astral's linter
```

## Running the Application

### Development mode (with hot-reload)

```bash
uvicorn second_hand.main:app --reload
```

The dashboard will be available at http://localhost:8000

### Production mode

```bash
uvicorn second_hand.main:app --host 0.0.0.0 --port 8000
```

## Type Checking

Run ty for fast type checking:

```bash
ty check src/
```

Or check the entire project:

```bash
ty check .
```

## Running Tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=second_hand --cov-report=term-missing
```

## Linting

```bash
ruff check .
ruff format .
```

## Configuration

Environment variables (all optional):

| Variable | Default | Description |
|----------|---------|-------------|
| `SECOND_HAND_DEBUG` | `false` | Enable debug mode |
| `SECOND_HAND_HOST` | `127.0.0.1` | Server bind address |
| `SECOND_HAND_PORT` | `8000` | Server bind port |

## Project Structure

```text
second-hand/
├── src/second_hand/       # Application source code
│   ├── main.py            # FastAPI app entry point
│   ├── config.py          # Configuration management
│   └── components/        # htpy HTML components (type-safe!)
│       ├── base.py        # Base layout
│       └── dashboard.py   # Dashboard page
├── static/css/            # Stylesheets
├── tests/                 # Test suite
│   ├── test_main.py       # API tests
│   ├── test_config.py     # Config tests
│   └── test_components.py # Component unit tests
├── pyproject.toml         # Project configuration
└── README.md              # Project documentation
```

## Development Workflow

1. Make changes to source files (components are Python, not templates!)
2. Browser auto-refreshes when using `--reload`
3. Run `ty check src/` for type validation
4. Run `pytest` to verify changes
5. Run `ruff check .` for linting
6. Commit and push to trigger CI

## Verification Checklist

After setup, verify:

- [ ] `uvicorn second_hand.main:app --reload` starts without errors
- [ ] http://localhost:8000 displays the dashboard
- [ ] `ty check src/` reports no type errors
- [ ] `pytest` runs and all tests pass
- [ ] Modifying a component and refreshing shows changes (dev mode)
- [ ] `ruff check .` passes with no errors

## Why htpy Instead of Jinja2?

This project uses [htpy](https://htpy.dev/) for type-safe HTML generation:

```python
# Type-safe, IDE-friendly, testable
from htpy import div, h1, p

def my_component(title: str) -> Element:
    return div(".card")[
        h1[title],
        p["Content here"]
    ]
```

Benefits:
- Full type checking with ty
- IDE auto-completion for HTML elements
- Refactoring updates all usages
- Unit test components directly (no regex on rendered HTML)

## Tooling Stack (Astral)

This project uses [Astral](https://astral.sh/) tools for a modern, fast development experience:

| Tool | Purpose | Speed |
|------|---------|-------|
| [uv](https://docs.astral.sh/uv/) | Package management | 10-100x faster than pip |
| [ty](https://docs.astral.sh/ty/) | Type checking | 10-60x faster than mypy |
| [ruff](https://docs.astral.sh/ruff/) | Linting + formatting | 10-100x faster than flake8 |
