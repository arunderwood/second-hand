"""Dashboard page component for second-hand."""

from htpy import Element, div, h1, h2, p, section

from .base import base_layout


def dashboard_page(version: str) -> Element:
    """Create the main dashboard page.

    Args:
        version: Application version string to display.

    Returns:
        Complete HTML dashboard page as an htpy Element.
    """
    content = div(".dashboard")[
        _header(version),
        _stats_section(),
        _footer(version),
    ]
    return base_layout("second-hand Dashboard", content)


def _header(version: str) -> Element:
    """Create the dashboard header."""
    return div(".dashboard-header")[
        h1(".dashboard-title")["second-hand"],
        p(".dashboard-subtitle")["Chrony Time Statistics Dashboard"],
    ]


def _stats_section() -> Element:
    """Create the statistics section with placeholder content."""
    return section(".stats-section")[
        h2(".stats-title")["Time Statistics"],
        div(".stats-grid")[
            _stat_card("System Time", "Awaiting connection"),
            _stat_card("NTP Sources", "Awaiting connection"),
            _stat_card("Stratum", "Awaiting connection"),
            _stat_card("Last Update", "Awaiting connection"),
        ],
        p(".stats-placeholder")[
            "Chrony time statistics will appear here once connected."
        ],
    ]


def _stat_card(title: str, value: str) -> Element:
    """Create a statistics display card."""
    return div(".stat-card")[
        div(".stat-title")[title],
        div(".stat-value")[value],
    ]


def _footer(version: str) -> Element:
    """Create the dashboard footer."""
    return div(".dashboard-footer")[p(".version")[f"Version {version}"],]
