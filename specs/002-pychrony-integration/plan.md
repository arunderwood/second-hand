# Implementation Plan: Pychrony Dashboard Integration

**Branch**: `002-pychrony-integration` | **Date**: 2026-01-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-pychrony-integration/spec.md`

## Summary

Integrate the pychrony library into second-hand to display all four chrony data sources (tracking status, sources, source statistics, RTC data) on the dashboard. The integration includes high-value metric boxes for key indicators, tabular displays for detailed data, graceful error handling, and Docker Compose-based integration tests that run in CI.

## Technical Context

**Language/Version**: Python 3.14 (primary), matrix testing 3.13, 3.12
**Primary Dependencies**: FastAPI, uvicorn, htpy (type-safe HTML), pychrony (from PyPI Test)
**Storage**: N/A (read-only queries to chronyd via socket)
**Testing**: pytest (unit), Docker Compose + pytest (integration)
**Target Platform**: Linux server (chronyd requirement)
**Project Type**: Single web application
**Performance Goals**: Dashboard loads within 2 seconds
**Constraints**: <100MB memory, single process, read-only chrony access
**Scale/Scope**: Single-user homelab dashboard

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Security First | ✅ PASS | Read-only pychrony calls; no user input to chrony; pychrony handles socket communication securely |
| II. Lightweight Design | ✅ PASS | pychrony is single dependency addition; no polling (fresh fetch on page load); single process |
| III. Simple Setup | ✅ PASS | pip/uv install with pychrony bundled wheels; works with sensible defaults |
| IV. Focused Scope | ✅ PASS | Displays chrony statistics only; read-only via pychrony; no configuration changes |
| V. Learning-Friendly Code | ✅ PASS | Type hints throughout; structured components; clear separation of concerns |

**Gate Result**: PASS - All principles satisfied. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/002-pychrony-integration/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/second_hand/
├── __init__.py
├── main.py              # FastAPI app with dashboard route
├── config.py            # Application configuration
├── services/            # NEW: Service layer for pychrony
│   ├── __init__.py
│   └── chrony.py        # Chrony data fetching service
└── components/
    ├── __init__.py
    ├── base.py          # Base HTML layout
    ├── dashboard.py     # MODIFY: Integrate chrony data display
    ├── tracking.py      # NEW: Tracking status component
    ├── sources.py       # NEW: Sources table component
    ├── stats.py         # NEW: Source statistics component
    └── rtc.py           # NEW: RTC data component

tests/
├── unit/                # NEW: Unit tests
│   ├── __init__.py
│   └── test_chrony_service.py
└── integration/         # NEW: Integration tests
    ├── __init__.py
    ├── conftest.py
    └── test_chrony_integration.py

docker/                  # NEW: Docker Compose for integration tests
├── docker-compose.test.yml
├── Dockerfile.test
└── chrony.conf
```

**Structure Decision**: Extends existing single-project structure with new `services/` layer for pychrony integration and dedicated `docker/` directory for integration test infrastructure.

## Complexity Tracking

> No violations - all principles satisfied.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
