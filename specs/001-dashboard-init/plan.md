# Implementation Plan: Dashboard Initialization

**Branch**: `001-dashboard-init` | **Date**: 2026-01-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-dashboard-init/spec.md`

## Summary

Initialize the Python project structure for a chrony time statistics dashboard. This phase establishes the foundation: a FastAPI web server serving a modern, visually sharp dashboard page with placeholder content using htpy for type-safe HTML generation, development mode with hot-reload, pytest testing framework with example tests, GitHub Actions CI workflow with Python version matrix (3.14, 3.13, 3.12), Dependabot configuration, and comprehensive README documentation. No chrony integration in this phase.

## Technical Context

**Language/Version**: Python 3.14 (primary), matrix testing 3.13, 3.12
**Primary Dependencies**: FastAPI, uvicorn, htpy (type-safe HTML)
**Type Checking**: Astral ty (beta, 10-60x faster than mypy)
**Storage**: N/A (static page, no persistence)
**Testing**: pytest, pytest-cov, httpx (async test client)
**Target Platform**: Linux server (homelab), also macOS/Windows for development
**Project Type**: Web application (single-process ASGI server)
**Performance Goals**: Page load <2 seconds, dev mode refresh <5 seconds
**Constraints**: <100MB memory (Constitution II), single process (Constitution II)
**Scale/Scope**: Single dashboard page, single developer initially

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Security First | PASS | No external inputs beyond HTTP routes; no user data; static content only |
| II. Lightweight Design | PASS | Minimal deps (FastAPI, htpy, uvicorn); single process; no database |
| III. Simple Setup | PASS | Single `pip install` + `uvicorn` command; sensible defaults |
| IV. Focused Scope | PASS | Dashboard display only; no chrony config; read-only future |
| V. Learning-Friendly Code | PASS | Type hints required; ty type checking; htpy provides type-safe HTML |

**Technical Constraints Compliance**:
- Python 3.14: PASS (cutting edge, stable October 2025)
- FastAPI: PASS
- pychrony: N/A (out of scope for this phase)
- Single-process uvicorn: PASS
- No subprocess with user input: PASS (no user input)
- No eval/exec: PASS
- No hardcoded secrets: PASS (no secrets needed)

**Gate Result**: PASS - Proceed to Phase 0

## Project Structure

### Documentation (this feature)

```text
specs/001-dashboard-init/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── second_hand/
│   ├── __init__.py
│   ├── main.py          # FastAPI application entry point
│   ├── config.py        # Configuration management
│   └── components/
│       ├── __init__.py
│       ├── base.py      # Base layout component (htpy)
│       └── dashboard.py # Dashboard page component (htpy)
├── static/
│   └── css/
│       └── style.css    # Dashboard styling
tests/
├── __init__.py
├── conftest.py          # pytest fixtures
├── test_main.py         # Application tests
├── test_config.py       # Configuration tests
└── test_components.py   # Component unit tests (type-safe!)

pyproject.toml           # Project configuration and dependencies
README.md                # Project documentation
.github/
├── workflows/
│   └── ci.yml           # GitHub Actions CI workflow (Python 3.14, 3.13, 3.12)
└── dependabot.yml       # Dependency update configuration (no PR limit)
```

**Structure Decision**: Single web application structure with htpy components instead of Jinja2 templates. The `src/second_hand/components/` directory contains type-safe Python functions that generate HTML, enabling full IDE support, refactoring safety, and unit testing without regex matching on rendered output.

## Complexity Tracking

> No Constitution violations - table not needed.
