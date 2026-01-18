# API Contract: Dashboard

**Date**: 2026-01-17
**Feature**: 002-pychrony-integration

## Overview

The second-hand dashboard is a server-rendered HTML application. There is no REST API - the dashboard route returns complete HTML pages with embedded chrony data. This contract documents the HTTP interface and the service layer interface.

## HTTP Endpoints

### GET /

**Description**: Main dashboard page with all chrony data displayed.

**Response**: HTML page (text/html)

**Behavior**:
- Fetches fresh chrony data on each request
- Returns dashboard with populated data sections if chronyd accessible
- Returns dashboard with error message if chronyd not accessible
- Always returns 200 OK (errors shown in page content)

**Response States**:

| State | Page Content |
|-------|--------------|
| Connected & Synchronized | Full dashboard with all data sections |
| Connected & Unsynchronized | Dashboard with stratum=16, no reference source |
| Connection Error | Error banner with guidance message |
| Permission Denied | Error banner suggesting chrony group membership |
| RTC Unavailable | RTC section shows "not configured" message |

## Service Layer Interface

### fetch_chrony_data()

**Signature**:
```python
def fetch_chrony_data(socket_path: str | None = None) -> ChronyData:
    """
    Fetch all chrony data from chronyd.

    Args:
        socket_path: Optional custom socket path. Uses pychrony default if None.

    Returns:
        ChronyData with all available data and any error message.
    """
```

**Behavior**:
1. Call `get_tracking()` - if fails, set error and return early
2. Call `get_sources()` - collect results
3. Call `get_source_stats()` - collect results
4. Call `get_rtc_data()` - if fails with ChronyDataError, set rtc=None (not an error)
5. Return aggregated ChronyData

**Error Mapping**:

| pychrony Exception | ChronyData.error |
|--------------------|------------------|
| ChronyConnectionError | "Unable to connect to chronyd. Is the service running?" |
| ChronyPermissionError | "Permission denied. Add your user to the chrony group." |
| ChronyLibraryError | "pychrony library error. Check installation." |
| ChronyDataError (RTC only) | rtc=None, no error (RTC is optional) |

## Component Interfaces

### tracking_section(data: ChronyData) -> Element

Renders the tracking status section with stat boxes.

**High-Value Metrics** (stat boxes):
- Sync Status: "Synchronized" / "Not Synchronized"
- Offset: Formatted as ms/µs with sign
- Stratum: Integer 0-15 (or 16 if unsync)
- Reference: Source name or "None"

### sources_table(sources: list[Source]) -> Element

Renders the NTP sources table.

**Columns**:
| Column | Source Field | Format |
|--------|--------------|--------|
| Address | address | As-is |
| State | state | Enum name (e.g., "Selected") |
| Stratum | stratum | Integer |
| Poll | poll | 2^poll seconds |
| Reach | reachability | Octal (e.g., "377") |
| Last Rx | last_sample_ago | Human-readable duration |

**Row Styling**:
- Selected source: highlighted row
- Unreachable source: dimmed row

### stats_table(stats: list[SourceStats]) -> Element

Renders the source statistics table.

**Columns**:
| Column | SourceStats Field | Format |
|--------|-------------------|--------|
| Address | address | As-is |
| Samples | samples | Integer |
| Offset | offset | Formatted as ms/µs |
| Std Dev | std_dev | Scientific notation |
| Skew | skew | ppm |

### rtc_section(rtc: RTCData | None) -> Element

Renders the RTC data section.

**If rtc is None**: Display "RTC tracking not configured" message.

**If rtc is available**:
| Metric | RTCData Field | Format |
|--------|---------------|--------|
| Offset | offset | Seconds with sign |
| Drift | freq_offset | ppm |
| Samples | samples | Integer |

### error_banner(message: str) -> Element

Renders an error banner at the top of the dashboard.

**Content**: Error message with icon and suggested action.

## Value Formatting

### Offset Formatting

```python
def format_offset(seconds: float) -> str:
    """Format offset for human readability."""
    abs_val = abs(seconds)
    if abs_val >= 1:
        return f"{seconds:+.3f} s"
    elif abs_val >= 0.001:
        return f"{seconds * 1000:+.3f} ms"
    else:
        return f"{seconds * 1_000_000:+.1f} µs"
```

### Duration Formatting

```python
def format_duration(seconds: int) -> str:
    """Format duration for human readability."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
```

### Reachability Formatting

```python
def format_reachability(value: int) -> str:
    """Format reachability as octal."""
    return f"{value:03o}"
```
