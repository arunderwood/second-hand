# Research: Dashboard Initialization

**Feature**: 001-dashboard-init
**Date**: 2026-01-17
**Updated**: 2026-01-17 (Modern stack revision)

## Technology Decisions

### 1. Python Version: 3.14 Primary, Matrix to 3.12

**Decision**: Use Python 3.14 as primary version with CI matrix testing down to 3.12

**Rationale**:
- Python 3.14 released October 2025, stable and production-ready
- Bugfix support through ~2027, security support through October 2030
- Latest language features and performance improvements
- 3.13 provides excellent fallback (2+ years full support)
- 3.12 ensures broad compatibility (proven, mature)

**Alternatives Considered**:
- Python 3.11: Still supported but missing newer features; unnecessary constraint
- Python 3.13 only: Would miss 3.14 improvements without good reason

**References**: [PEP 745: Python 3.14 Release Schedule](https://peps.python.org/pep-0745/)

### 2. Type Checking: Astral ty

**Decision**: Use [Astral ty](https://astral.sh/blog/ty) for type checking

**Rationale**:
- 10-60x faster than mypy (2.19s vs 45.66s on Home Assistant)
- 80x faster incremental updates than Pyright (4.7ms vs 386ms)
- Written in Rust by Astral (creators of ruff and uv)
- Beta status but production-ready (Astral uses it internally)
- Built-in Language Server Protocol support
- Targeting stable 1.0 release in 2026

**Alternatives Considered**:
- mypy: Industry standard but significantly slower
- Pyright: Fast but ty is faster for incremental updates
- No type checking: Unacceptable for modern Python project

**Installation**: `uv tool install ty@latest` or VS Code extension

**References**: [ty Documentation](https://docs.astral.sh/ty/), [GitHub](https://github.com/astral-sh/ty)

### 3. HTML Generation: htpy (Type-Safe)

**Decision**: Use [htpy](https://htpy.dev/) instead of Jinja2 templating

**Rationale**:
- **Type Safety**: Full mypy/Pyright/ty support - HTML elements are typed Python objects
- **IDE Support**: Auto-completion, go-to-definition, refactoring for HTML
- **Testing**: Unit test components directly as Python functions, no regex on rendered HTML
- **Modern Pattern**: React-inspired composition (children as `[]`, attributes as `()`)
- **Lightweight**: Minimal library, no template compilation overhead
- **Learning-Friendly**: Aligns with Constitution V - clear, debuggable Python code

**Jinja2 is NOT antiquated** - it's battle-tested and works well. However, htpy provides significant advantages for a type-safe codebase:

| Feature | htpy | Jinja2 |
|---------|------|--------|
| Type Safety | Full | None |
| IDE Support | Complete | Limited |
| Refactoring | Safe | Manual |
| Testing | Direct | Regex/parsing |
| Learning Curve | Python knowledge | Template syntax |
| Dependencies | Minimal | Included in FastAPI |

**Example**:
```python
from htpy import html, head, title, body, div, h1, p

def dashboard_page(version: str) -> Element:
    return html[
        head[title["second-hand Dashboard"]],
        body[
            div(".container")[
                h1["Chrony Time Statistics"],
                p[f"Version {version} - Awaiting chrony connection"]
            ]
        ]
    ]
```

**Alternatives Considered**:
- **Jinja2**: Works but no type safety; feels antiquated for type-first development
- **FastHTML**: Full framework replacement, not just templating; overkill when FastAPI works
- **dominate**: Similar concept but htpy has better typing and more active development
- **React/Vue SPA**: Over-engineered for a homelab dashboard

**References**: [htpy Documentation](https://htpy.dev/), [GitHub](https://github.com/pelme/htpy), [Static Typing Guide](https://htpy.dev/static-typing/)

### 4. Web Framework: FastAPI (Unchanged)

**Decision**: Use FastAPI as the web framework

**Rationale**:
- Constitution mandates FastAPI (Technical Constraints)
- Native async support aligns with uvicorn ASGI server
- Built-in OpenAPI documentation
- Excellent developer experience with type hints
- Lightweight footprint (Constitution II compliance)
- htpy integrates seamlessly (return HTML as string response)

**References**: [FastAPI Documentation](https://fastapi.tiangolo.com/)

### 5. Development Mode: Uvicorn --reload

**Decision**: Use uvicorn's built-in `--reload` flag for development hot-reload

**Rationale**:
- Zero additional dependencies
- Watches Python files automatically
- htpy components reload on file save (no template caching issues)
- Standard practice for FastAPI development
- Production mode simply omits the flag (clear separation per FR-009)

### 6. Testing Framework: pytest

**Decision**: Use pytest with httpx for async testing

**Rationale**:
- pytest is the Python testing standard
- httpx provides `AsyncClient` for testing FastAPI apps
- pytest-cov for coverage reporting in CI
- **htpy bonus**: Components can be unit tested directly as Python functions

**Testing Pattern with htpy**:
```python
from second_hand.components.dashboard import dashboard_page

def test_dashboard_page_contains_version():
    result = str(dashboard_page(version="0.1.0"))
    assert "0.1.0" in result
    assert "Chrony Time Statistics" in result
```

### 7. Project Structure: src layout with components/

**Decision**: Use `src/second_hand/components/` for htpy components

**Rationale**:
- Replaces `templates/` directory with type-safe Python modules
- Each component is a Python function returning htpy elements
- Full IDE support, refactoring, and testing
- Clear separation: `components/base.py` (layout), `components/dashboard.py` (page)

### 8. CSS Approach: Custom CSS (no framework)

**Decision**: Write custom CSS for the dashboard styling

**Rationale**:
- Lightweight (Constitution II)
- Full control over "modern, sharp" aesthetic suited for time statistics
- CSS custom properties (variables) for theming flexibility
- Responsive design via CSS Grid/Flexbox
- htpy supports class attributes: `div(".container.card")["content"]`

### 9. CI Configuration: GitHub Actions with Python Matrix

**Decision**: Use GitHub Actions with Python version matrix (3.14, 3.13, 3.12)

**Rationale**:
- Constitution assumes GitHub hosting
- Matrix testing ensures compatibility across Python versions
- Primary version (3.14) runs first for fast feedback
- Include ty type checking in CI

**Workflow Components**:
- Trigger: push/PR to main and feature branches
- Python matrix: 3.14, 3.13, 3.12
- Dependency caching via pip cache
- ty type checking
- pytest with coverage
- Fail on test failures or type errors

### 10. Dependency Management: Dependabot (No PR Limit)

**Decision**: Configure Dependabot for daily Python updates with no PR limit

**Rationale**:
- Native GitHub feature
- Automatic security update PRs
- Daily schedule as specified in requirements
- **No open PR limit** as requested (allows all updates to create PRs)

**Configuration**:
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "daily"
    # No open-pull-requests-limit (defaults to unlimited)
```

## Best Practices Applied

### FastAPI + htpy Pattern

```python
# main.py
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from second_hand.components.dashboard import dashboard_page

app = FastAPI(title="second-hand")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    return str(dashboard_page(version="0.1.0"))
```

### htpy Component Pattern

```python
# components/base.py
from htpy import Element, html, head, title, meta, link, body

def base_layout(page_title: str, content: Element) -> Element:
    return html(lang="en")[
        head[
            meta(charset="utf-8"),
            meta(name="viewport", content="width=device-width, initial-scale=1"),
            title[page_title],
            link(rel="stylesheet", href="/static/css/style.css"),
        ],
        body[content]
    ]
```

```python
# components/dashboard.py
from htpy import Element, div, h1, p, section

from .base import base_layout

def dashboard_page(version: str) -> Element:
    content = div(".dashboard")[
        h1["second-hand Dashboard"],
        section(".stats-placeholder")[
            p["Chrony time statistics will appear here."],
            p(".version")[f"Version {version}"]
        ]
    ]
    return base_layout("second-hand Dashboard", content)
```

### Configuration Pattern

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000

    class Config:
        env_prefix = "SECOND_HAND_"
```

### Testing Pattern

```python
# test_components.py
from second_hand.components.dashboard import dashboard_page
from second_hand.components.base import base_layout

def test_dashboard_page_structure():
    page = dashboard_page(version="1.0.0")
    html = str(page)
    assert "second-hand Dashboard" in html
    assert "Version 1.0.0" in html
    assert "Chrony time statistics" in html

def test_base_layout_includes_title():
    from htpy import p
    page = base_layout("Test Page", p["content"])
    html = str(page)
    assert "<title>Test Page</title>" in html
```

## Dependency Versions (Cutting Edge, Stable)

| Package | Version | Status | Notes |
|---------|---------|--------|-------|
| Python | 3.14 | Stable | Released Oct 2025 |
| FastAPI | 0.115+ | Stable | Latest async improvements |
| uvicorn | 0.34+ | Stable | HTTP/2, improved reload |
| htpy | 25.10+ | Stable | Latest release |
| pydantic | 2.10+ | Stable | Settings validation |
| pydantic-settings | 2.7+ | Stable | Environment config |
| pytest | 8.3+ | Stable | Latest fixtures |
| httpx | 0.28+ | Stable | Async client |
| pytest-cov | 6.0+ | Stable | Coverage reporting |

**Development Tools**:
| Tool | Version | Status | Notes |
|------|---------|--------|-------|
| ty | 0.0.12+ | Beta | Type checking (Astral) |
| ruff | 0.9+ | Stable | Linting (Astral) |
| uv | 0.5+ | Stable | Package management (Astral) |

## Open Questions Resolved

All technical decisions have been made. No outstanding NEEDS CLARIFICATION items.

## References

- [ty Type Checker](https://astral.sh/blog/ty) - Astral's fast Python type checker
- [htpy Documentation](https://htpy.dev/) - Type-safe HTML in Python
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Python 3.14 What's New](https://docs.python.org/3/whatsnew/3.14.html)
- [pytest Documentation](https://docs.pytest.org/)
- [GitHub Actions](https://docs.github.com/en/actions)
- [Dependabot Configuration](https://docs.github.com/en/code-security/dependabot)
