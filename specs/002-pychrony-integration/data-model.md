# Data Model: Pychrony Dashboard Integration

**Date**: 2026-01-17
**Feature**: 002-pychrony-integration

## Overview

This feature uses pychrony's existing data models (frozen dataclasses) and adds a wrapper type for dashboard rendering. No database storage is involved - all data is fetched fresh from chronyd on each page load.

## External Models (from pychrony)

These models are provided by pychrony and used as-is:

### TrackingStatus

Current time synchronization state from chronyd.

| Field | Type | Description |
|-------|------|-------------|
| reference_id | int | NTP reference identifier (uint32) |
| reference_id_name | str | Human-readable reference source name |
| reference_ip | str | IP address of reference source |
| stratum | int | NTP stratum level (0-15, 16=unsync) |
| leap_status | LeapStatus | Leap second status enum |
| ref_time | float | Timestamp of last measurement (epoch) |
| offset | float | Current offset in seconds |
| last_offset | float | Offset at last measurement |
| rms_offset | float | RMS of recent offsets |
| frequency | float | Clock frequency error (ppm) |
| residual_freq | float | Residual frequency (ppm) |
| skew | float | Frequency error bound (ppm) |
| root_delay | float | Roundtrip delay to stratum-1 |
| root_dispersion | float | Dispersion to reference |
| update_interval | float | Seconds since last update |

**Helper Methods**:
- `is_synchronized() -> bool` - True if reference_id != 0 and stratum < 16
- `is_leap_pending() -> bool` - True if leap_status is INSERT or DELETE

### Source

NTP time source information.

| Field | Type | Description |
|-------|------|-------------|
| address | str | IP address or refclock ID |
| poll | int | Polling interval (log2 seconds) |
| stratum | int | Source stratum level |
| state | SourceState | Selection state enum |
| mode | SourceMode | Source mode enum |
| flags | int | Source flags bitfield |
| reachability | int | Reachability register (0-255) |
| last_sample_ago | int | Seconds since last sample |
| orig_latest_meas | float | Original last sample offset |
| latest_meas | float | Adjusted last sample offset |
| latest_meas_err | float | Last sample error bound |

**Helper Methods**:
- `is_reachable() -> bool` - True if reachability > 0
- `is_selected() -> bool` - True if state is SELECTED

### SourceStats

Statistical data for a source.

| Field | Type | Description |
|-------|------|-------------|
| reference_id | int | NTP reference identifier |
| address | str | Source IP address |
| samples | int | Number of retained samples |
| runs | int | Runs of same-sign residuals |
| span | int | Time span of samples (seconds) |
| std_dev | float | Sample standard deviation |
| resid_freq | float | Residual frequency (ppm) |
| skew | float | Frequency skew (ppm) |
| offset | float | Estimated offset |
| offset_err | float | Offset error bound |

**Helper Methods**:
- `has_sufficient_samples(minimum=4) -> bool` - True if samples >= minimum

### RTCData

Hardware RTC information.

| Field | Type | Description |
|-------|------|-------------|
| ref_time | float | RTC reading at last measurement |
| samples | int | Calibration sample count |
| runs | int | Runs of residuals |
| span | int | Measurement time span |
| offset | float | RTC offset (seconds) |
| freq_offset | float | RTC frequency drift (ppm) |

**Helper Methods**:
- `is_calibrated() -> bool` - True if samples > 0

## Enums (from pychrony)

### LeapStatus

| Value | Name | Description |
|-------|------|-------------|
| 0 | NORMAL | No leap second pending |
| 1 | INSERT | Leap second insert at midnight |
| 2 | DELETE | Leap second delete at midnight |
| 3 | UNSYNC | Clock unsynchronized |

### SourceState

| Value | Name | Description |
|-------|------|-------------|
| 0 | SELECTED | Currently selected for sync |
| 1 | NONSELECTABLE | Cannot be selected |
| 2 | FALSETICKER | Detected as incorrect |
| 3 | JITTERY | Excessive jitter |
| 4 | UNSELECTED | Valid but not selected |
| 5 | SELECTABLE | Candidate for selection |

### SourceMode

| Value | Name | Description |
|-------|------|-------------|
| 0 | CLIENT | NTP client to server |
| 1 | PEER | NTP peer relationship |
| 2 | REFCLOCK | Local reference clock |

## Application Models (new)

### ChronyData

Aggregated container for all chrony data, used for dashboard rendering.

```python
@dataclass
class ChronyData:
    """Container for all chrony data fetched for dashboard display."""
    tracking: TrackingStatus | None
    sources: list[Source]
    source_stats: list[SourceStats]
    rtc: RTCData | None
    error: str | None

    @property
    def is_connected(self) -> bool:
        """Check if successfully connected to chronyd."""
        return self.error is None and self.tracking is not None

    @property
    def is_synchronized(self) -> bool:
        """Check if system is synchronized."""
        return self.tracking is not None and self.tracking.is_synchronized()
```

| Field | Type | Description |
|-------|------|-------------|
| tracking | TrackingStatus \| None | Tracking status (None on error) |
| sources | list[Source] | List of sources (empty on error) |
| source_stats | list[SourceStats] | List of stats (empty on error) |
| rtc | RTCData \| None | RTC data (None if unavailable) |
| error | str \| None | Error message if connection failed |

## Data Flow

```
┌─────────────────┐
│   HTTP Request  │
│  GET /dashboard │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ chrony.service  │
│ fetch_chrony_   │
│     data()      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│    pychrony     │────►│    chronyd      │
│  get_tracking() │     │ (Unix socket)   │
│  get_sources()  │     └─────────────────┘
│  get_source_    │
│     stats()     │
│  get_rtc_data() │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   ChronyData    │
│  (aggregated)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Components    │
│  tracking.py    │
│  sources.py     │
│  stats.py       │
│  rtc.py         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   HTML Response │
└─────────────────┘
```

## Validation Rules

All validation is handled by pychrony at the binding layer. The application layer:

1. **Does not modify** pychrony dataclass values
2. **Does not validate** field ranges (trusted from chronyd)
3. **Does handle** None/empty cases for display
4. **Does format** values for human readability (e.g., offset in ms/µs)
