"""Dashboard page component for second-hand."""

from htpy import Element, div, h1, p

from second_hand.services.chrony import ChronyData, EnrichedSource, fetch_chrony_data

from .base import base_layout
from .error import error_banner
from .rtc import rtc_section
from .sources import sources_table
from .stats import stats_table
from .tracking import tracking_section


def dashboard_page(
    version: str,
    chrony_data: ChronyData | None = None,
    enriched_sources: list[EnrichedSource] | None = None,
) -> Element:
    """Create the main dashboard page.

    Args:
        version: Application version string to display.
        chrony_data: Optional pre-fetched chrony data. If None, fetches fresh data.
        enriched_sources: Optional enriched sources with hostname/geo data.

    Returns:
        Complete HTML dashboard page as an htpy Element.
    """
    # Fetch chrony data if not provided
    data = chrony_data if chrony_data is not None else fetch_chrony_data()

    content = div(".dashboard")[
        _header(version),
        _main_content(data, enriched_sources),
        _footer(version),
    ]
    return base_layout("second-hand Dashboard", content)


def _header(version: str) -> Element:
    """Create the dashboard header."""
    return div(".dashboard-header")[
        h1(".dashboard-title")["second-hand"],
        p(".dashboard-subtitle")["Chrony Time Statistics Dashboard"],
    ]


def _main_content(
    data: ChronyData, enriched_sources: list[EnrichedSource] | None = None
) -> Element:
    """Create the main content area with all chrony sections."""
    sections: list[Element] = []

    # Show error banner if there's a connection error
    if data.error:
        sections.append(error_banner(data.error))

    # Always show tracking section (handles None tracking gracefully)
    sections.append(tracking_section(data))

    # Only show other sections if we have data
    if data.is_connected:
        if enriched_sources:
            # Use enriched sources if available (with hostname/geo data)
            sections.append(sources_table(enriched_sources))
        elif data.sources:
            # Fall back to raw sources
            sections.append(sources_table(data.sources))
        if data.source_stats:
            sections.append(stats_table(data.source_stats))
        # RTC section handles None gracefully
        sections.append(rtc_section(data.rtc))

    return div(".main-content")[sections]


def _footer(version: str) -> Element:
    """Create the dashboard footer."""
    return div(".dashboard-footer")[p(".version")[f"Version {version}"],]
