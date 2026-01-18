"""Utility functions for second-hand."""

__all__ = ["format_offset", "format_duration", "format_reachability"]


def format_offset(seconds: float) -> str:
    """Format offset for human readability.

    Args:
        seconds: Offset in seconds.

    Returns:
        Human-readable offset string with appropriate unit.
    """
    abs_val = abs(seconds)
    if abs_val >= 1:
        return f"{seconds:+.3f} s"
    elif abs_val >= 0.001:
        return f"{seconds * 1000:+.3f} ms"
    else:
        return f"{seconds * 1_000_000:+.1f} \u00b5s"


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
