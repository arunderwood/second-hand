"""Utility functions for second-hand."""

from datetime import UTC, datetime
from typing import Literal

__all__ = [
    "format_offset",
    "format_duration",
    "format_reachability",
    "format_timestamp",
    "format_frequency",
    "format_reachability_visual",
    "get_health_status",
    "country_code_to_flag",
]

# Health status thresholds based on industry-standard NTP values
_HEALTH_THRESHOLDS: dict[str, tuple[float, float]] = {
    # (warning_threshold, error_threshold) - values below warning are "healthy"
    "offset": (0.010, 0.100),  # 10ms warning, 100ms error
    "rms_offset": (0.001, 0.010),  # 1ms warning, 10ms error
    "frequency": (10.0, 50.0),  # 10ppm warning, 50ppm error
    "skew": (1.0, 5.0),  # 1ppm warning, 5ppm error
    "root_delay": (0.050, 0.100),  # 50ms warning, 100ms error
    "root_dispersion": (0.010, 0.050),  # 10ms warning, 50ms error
}

_STRATUM_THRESHOLDS = (3, 8)  # warning if > 3, error if > 8 or == 16

HealthStatus = Literal["healthy", "warning", "error"]


def format_offset(seconds: float) -> str:
    """Format offset for human readability.

    Uses adaptive scaling: s -> ms -> us -> ns based on magnitude.

    Args:
        seconds: Offset in seconds.

    Returns:
        Human-readable offset string with appropriate unit and sign.
    """
    abs_val = abs(seconds)
    if abs_val >= 1:
        return f"{seconds:+.3f} s"
    elif abs_val >= 0.001:
        return f"{seconds * 1000:+.3f} ms"
    elif abs_val >= 0.000001:
        return f"{seconds * 1_000_000:+.1f} \u00b5s"
    else:
        return f"{seconds * 1_000_000_000:+.0f} ns"


def format_duration(seconds: int) -> str:
    """Format duration for human readability.

    Args:
        seconds: Duration in seconds.

    Returns:
        Human-readable duration string.
    """
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


def format_reachability(value: int) -> str:
    """Format reachability as octal.

    Args:
        value: Reachability register value (0-255).

    Returns:
        Three-digit octal string.
    """
    return f"{value:03o}"


def format_timestamp(epoch: float) -> str:
    """Format epoch timestamp for human readability.

    Args:
        epoch: Unix timestamp in seconds.

    Returns:
        Human-readable timestamp string in UTC.
    """
    dt = datetime.fromtimestamp(epoch, tz=UTC)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def format_frequency(ppm: float) -> str:
    """Format frequency offset in parts per million.

    Args:
        ppm: Frequency offset in ppm.

    Returns:
        Formatted frequency string with sign and unit.
    """
    return f"{ppm:+.3f} ppm"


def format_reachability_visual(value: int) -> list[bool]:
    """Convert reachability register to visual bit representation.

    The reachability register is an 8-bit value where each bit represents
    one of the last 8 poll attempts (bit 0 = most recent).

    Args:
        value: Reachability register value (0-255).

    Returns:
        List of 8 booleans, oldest to newest (left to right display).
        True = successful poll, False = failed poll.
    """
    # Extract bits from MSB to LSB for left-to-right display
    # Bit 7 (oldest) to bit 0 (newest)
    return [(value >> (7 - i)) & 1 == 1 for i in range(8)]


def get_health_status(metric: str, value: float) -> HealthStatus:
    """Evaluate health status based on metric thresholds.

    Args:
        metric: Name of the metric to evaluate. Supported metrics:
            - offset, rms_offset: time offsets (in seconds)
            - frequency, skew: frequency metrics (in ppm)
            - root_delay, root_dispersion: network metrics (in seconds)
            - stratum: hop count (integer)
            - reachability: octal register value (0-255)
        value: The metric value to evaluate.

    Returns:
        Health status: "healthy", "warning", or "error".
    """
    # Handle stratum specially (integer thresholds, 16 = unsynchronized)
    if metric == "stratum":
        int_value = int(value)
        if int_value == 16:
            return "error"
        if int_value > _STRATUM_THRESHOLDS[1]:
            return "error"
        if int_value > _STRATUM_THRESHOLDS[0]:
            return "warning"
        return "healthy"

    # Handle reachability (higher is better, 377 octal = 255 = all 8 successful)
    if metric == "reachability":
        int_value = int(value)
        if int_value < 0o177:  # Less than 127, high packet loss
            return "error"
        if int_value < 0o377:  # Less than 255, some packet loss
            return "warning"
        return "healthy"

    # Handle standard threshold-based metrics (lower absolute value is better)
    if metric in _HEALTH_THRESHOLDS:
        warning_threshold, error_threshold = _HEALTH_THRESHOLDS[metric]
        abs_value = abs(value)
        if abs_value >= error_threshold:
            return "error"
        if abs_value >= warning_threshold:
            return "warning"
        return "healthy"

    # Unknown metric - default to healthy
    return "healthy"


def country_code_to_flag(country_code: str | None) -> str:
    """Convert ISO 3166-1 alpha-2 country code to flag emoji.

    Uses Unicode Regional Indicator Symbols to convert a two-letter
    country code to its corresponding flag emoji.

    Args:
        country_code: Two-letter country code (e.g., "US", "GB", "DE"),
                     or None/empty string.

    Returns:
        Flag emoji string (e.g., "\U0001f1fa\U0001f1f8" for US flag),
        or empty string if input is invalid.

    Examples:
        >>> country_code_to_flag("US")
        '\U0001f1fa\U0001f1f8'
        >>> country_code_to_flag("GB")
        '\U0001f1ec\U0001f1e7'
        >>> country_code_to_flag(None)
        ''
        >>> country_code_to_flag("X")
        ''
    """
    if not country_code or len(country_code) != 2:
        return ""

    # Regional Indicator Symbol Letter A is at codepoint U+1F1E6 (127462)
    # We add 0x1F1A5 (127397) to ASCII uppercase letters to get the symbol
    # 'A' = 65, 65 + 127397 = 127462 = U+1F1E6
    try:
        return "".join(chr(ord(c.upper()) + 0x1F1A5) for c in country_code)
    except (TypeError, ValueError):
        return ""
