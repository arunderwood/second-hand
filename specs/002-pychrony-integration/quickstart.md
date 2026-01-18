# Quickstart: Pychrony Dashboard Integration

**Date**: 2026-01-17
**Feature**: 002-pychrony-integration

## Prerequisites

- Python 3.12+ (3.14 recommended)
- uv package manager
- Linux system with chronyd running (for full functionality)
- Docker (for running integration tests)

## Quick Setup

### 1. Install Dependencies

```bash
# Sync all dependencies including pychrony from Test PyPI
uv sync --all-extras --dev
```

### 2. Run Development Server

```bash
# Start the dashboard (will show error banner if chronyd not accessible)
uv run uvicorn second_hand.main:app --reload
```

Visit http://localhost:8000 to see the dashboard.

### 3. Run Tests

```bash
# Unit tests (no chronyd required)
uv run pytest tests/ -v --ignore=tests/integration

# Integration tests (requires Docker)
docker compose -f docker/docker-compose.test.yml run --rm test-integration
```

## Project Structure After Implementation

```
src/second_hand/
├── __init__.py
├── main.py                 # FastAPI app
├── config.py               # Settings
├── services/
│   ├── __init__.py
│   └── chrony.py          # fetch_chrony_data()
└── components/
    ├── __init__.py
    ├── base.py            # Base HTML layout
    ├── dashboard.py       # Main dashboard (updated)
    ├── tracking.py        # Tracking status boxes
    ├── sources.py         # Sources table
    ├── stats.py           # Source stats table
    └── rtc.py             # RTC data display

tests/
├── conftest.py
├── test_components.py     # Existing
├── test_config.py         # Existing
├── test_main.py           # Existing
├── unit/
│   ├── __init__.py
│   └── test_chrony_service.py
└── integration/
    ├── __init__.py
    ├── conftest.py
    └── test_chrony_integration.py

docker/
├── docker-compose.test.yml
├── Dockerfile.test
└── chrony.conf
```

## Key Files to Implement

### 1. services/chrony.py

Core service for fetching chrony data:

```python
from dataclasses import dataclass
from pychrony import (
    get_tracking, get_sources, get_source_stats, get_rtc_data,
    TrackingStatus, Source, SourceStats, RTCData,
    ChronyConnectionError, ChronyPermissionError, ChronyDataError,
)

@dataclass
class ChronyData:
    tracking: TrackingStatus | None
    sources: list[Source]
    source_stats: list[SourceStats]
    rtc: RTCData | None
    error: str | None

    @property
    def is_connected(self) -> bool:
        return self.error is None and self.tracking is not None

def fetch_chrony_data(socket_path: str | None = None) -> ChronyData:
    """Fetch all chrony data from chronyd."""
    try:
        tracking = get_tracking(socket_path=socket_path)
        sources = get_sources(socket_path=socket_path)
        source_stats = get_source_stats(socket_path=socket_path)
    except ChronyConnectionError:
        return ChronyData(None, [], [], None,
            "Unable to connect to chronyd. Is the service running?")
    except ChronyPermissionError:
        return ChronyData(None, [], [], None,
            "Permission denied. Add your user to the chrony group.")

    try:
        rtc = get_rtc_data(socket_path=socket_path)
    except ChronyDataError:
        rtc = None  # RTC tracking not configured

    return ChronyData(tracking, sources, source_stats, rtc, None)
```

### 2. pyproject.toml Changes

Add pychrony dependency with Test PyPI source:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "htpy>=25.10.0",
    "pydantic-settings>=2.7.0",
    "pychrony>=0.0.11",
]

[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"
explicit = true

[tool.uv.sources]
pychrony = { index = "testpypi" }
```

### 3. CI Workflow Update

Add integration test job to `.github/workflows/ci.yml`:

```yaml
integration-test:
  name: Integration Tests
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v6
    - name: Run integration tests
      run: docker compose -f docker/docker-compose.test.yml run --rm test-integration
```

## Testing Without chronyd

For local development without chronyd:

1. The dashboard will display an error banner
2. Unit tests mock the pychrony functions
3. Integration tests run in Docker with chronyd

## Verifying the Integration

After implementation, verify:

1. **Dashboard loads** - Visit http://localhost:8000
2. **Error handling works** - Stop chronyd, refresh page
3. **Data displays correctly** - Start chronyd, refresh page
4. **Unit tests pass** - `uv run pytest tests/unit -v`
5. **Integration tests pass** - `docker compose -f docker/docker-compose.test.yml run --rm test-integration`
6. **CI passes** - Push and check GitHub Actions
