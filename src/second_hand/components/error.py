"""Error banner component for displaying connection errors."""

from htpy import Element, div, p, span


def error_banner(message: str) -> Element:
    """Create an error banner for displaying at the top of the dashboard.

    Args:
        message: The error message to display.

    Returns:
        htpy Element containing the error banner.
    """
    return div(".error-banner")[
        span(".error-icon")["!"],
        div(".error-content")[p(".error-message")[message],],
    ]
