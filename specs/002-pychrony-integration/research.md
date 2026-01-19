# Research: Pychrony Dashboard Integration

**Date**: 2026-01-17
**Feature**: 002-pychrony-integration

## 1. pychrony API Usage Patterns

### Decision: Use pychrony's high-level functions directly

**Rationale**: pychrony provides four clean, typed functions that return frozen dataclasses. No wrapper needed.

**API Summary**:
```python
from pychrony import (
    get_tracking,      # Returns TrackingStatus
    get_sources,       # Returns list[Source]
    get_source_stats,  # Returns list[SourceStats]
    get_rtc_data,      # Returns RTCData (may raise ChronyDataError)
)
```

**Error Handling**:
- `ChronyConnectionError` - chronyd not running or socket inaccessible
- `ChronyPermissionError` - socket permission denied
- `ChronyDataError` - data unavailable (e.g., RTC not configured)
- `ChronyLibraryError` - libchrony not loaded

**Alternatives Considered**:
- Async wrapper: Rejected - pychrony calls are fast socket operations, no benefit from async
- Caching layer: Deferred - spec says fresh fetch, but architecture should support later addition

---

## 2. uv Configuration for PyPI Test Index

### Decision: Use `[[tool.uv.index]]` with explicit-index

**Rationale**: uv supports custom PyPI indexes with priority control. Using explicit assignment ensures pychrony comes from Test PyPI while other packages use default PyPI.

**Configuration** (pyproject.toml):
```toml
[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"
explicit = true

[tool.uv.sources]
pychrony = { index = "testpypi" }
```

**Key Points**:
- `explicit = true` means this index is only used when explicitly referenced
- Other dependencies automatically use default PyPI
- Works with `uv sync` and `uv pip install`

**Alternatives Considered**:
- `--extra-index-url` flag: Rejected - not declarative, harder to reproduce
- Vendoring pychrony: Rejected - spec explicitly requires PyPI Test sourcing

---

## 3. Docker Compose Integration Test Pattern

### Decision: Adapt pychrony's proven Docker test infrastructure

**Rationale**: pychrony already has working Docker Compose setup for integration testing with chronyd. Adapt the pattern for second-hand.

**Key Components**:

1. **Dockerfile.test**: Fedora-based image with chronyd pre-configured
   - Uses `local stratum 10` for predictable test behavior
   - Exposes Unix socket at `/run/chrony/chronyd.sock`
   - Requires `privileged: true` or `SYS_TIME` capability

2. **docker-compose.test.yml**: Service definitions
   - Start chronyd before tests with `chronyd && sleep 2`
   - Mount source/tests as volumes for fast iteration
   - Set `PYTHONPATH` for imports

3. **Test markers**: Use pytest marks for integration tests
   ```python
   @pytest.mark.integration
   def test_tracking_display():
       ...
   ```

**chrony.conf for testing**:
```
local stratum 10
allow 127.0.0.1
cmdallow 127.0.0.1
cmdport 0
bindcmdaddress /run/chrony/chronyd.sock
```

**Alternatives Considered**:
- Mock chronyd: Rejected - defeats purpose of integration testing
- System chronyd: Rejected - not portable across CI environments
- Alternative containers (Alpine): Rejected - Fedora has better chrony support

---

## 4. CI Integration for Docker Compose Tests

### Decision: Separate GitHub Actions job for integration tests

**Rationale**: Integration tests require Docker and are slower. Run in parallel with unit tests for efficiency.

**Workflow addition**:
```yaml
integration-test:
  name: Integration Tests
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v6
    - name: Run integration tests
      run: docker compose -f docker/docker-compose.test.yml run --rm test-integration
```

**Key Points**:
- Runs on ubuntu-latest (has Docker pre-installed)
- Uses `docker compose run` for one-shot test execution
- `--rm` cleans up container after tests
- Matrix testing not needed (Docker provides consistent environment)

**Alternatives Considered**:
- Services in workflow: Rejected - more complex, same result
- Local chronyd in CI: Rejected - requires sudo, less portable

---

## 5. Service Layer Architecture

### Decision: Thin service wrapper for error handling

**Rationale**: Dashboard needs to gracefully handle all error cases. Service layer centralizes error handling and provides consistent data structure for components.

**Pattern**:
```python
# services/chrony.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class ChronyData:
    tracking: Optional[TrackingStatus]
    sources: list[Source]
    source_stats: list[SourceStats]
    rtc: Optional[RTCData]
    error: Optional[str]

def fetch_chrony_data() -> ChronyData:
    """Fetch all chrony data, handling errors gracefully."""
    ...
```

**Benefits**:
- Single call for all data (fresh fetch per page load)
- Centralized error handling
- Easy to add caching later (wrap this function)
- Type-safe return value

**Alternatives Considered**:
- Separate fetch per section: Rejected - less efficient, harder to coordinate errors
- Direct pychrony calls in components: Rejected - duplicates error handling

---

## 6. htpy Component Patterns

### Decision: Separate component per data source with shared styling

**Rationale**: Existing dashboard uses htpy component pattern. Extend with new components for each pychrony data type.

**Component Structure**:
- `tracking.py` - Stat boxes for offset, stratum, sync status
- `sources.py` - Table of NTP sources
- `stats.py` - Table of source statistics
- `rtc.py` - RTC data display (or "not available" message)

**Shared Patterns**:
```python
def stat_box(title: str, value: str, status: str = "") -> Element:
    """Create a single-metric display box."""
    return div(".stat-box", {"data-status": status})[
        div(".stat-title")[title],
        div(".stat-value")[value],
    ]

def data_table(headers: list[str], rows: list[list[str]]) -> Element:
    """Create a data table with headers."""
    ...
```

**Alternatives Considered**:
- Single monolithic component: Rejected - harder to maintain and test
- JavaScript rendering: Rejected - unnecessary complexity for static display
