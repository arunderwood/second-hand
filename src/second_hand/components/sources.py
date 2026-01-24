"""Sources table component for displaying NTP sources."""

import time

from htpy import Element, div, h2, section, span, table, tbody, td, th, thead, tr
from pychrony import Source

from second_hand.components.base import tooltip_label
from second_hand.components.tooltips import SOURCE_TOOLTIPS
from second_hand.services.chrony import EnrichedSource
from second_hand.utils import (
    format_duration,
    format_offset,
    format_reachability,
    format_reachability_visual,
)


def sources_table(sources: list[Source] | list[EnrichedSource]) -> Element:
    """Create the NTP sources table section.

    Displays all configured NTP sources with mode, address, state, stratum,
    poll interval, reachability, last sample time, and measurement data.
    Table headers include tooltips explaining each column.
    Rows are styled based on source state (selected, falseticker, unreachable, jittery).

    Args:
        sources: List of Source or EnrichedSource objects.

    Returns:
        htpy Element containing the sources table section.
    """
    if not sources:
        return section(".sources-section")[
            h2(".section-title")["NTP Sources"],
            div(".empty-message")["No sources configured"],
        ]

    return section(".sources-section")[
        h2(".section-title")["NTP Sources"],
        table(".data-table")[
            thead[
                tr[
                    th[_header_with_tooltip("Mode", "mode")],
                    th["Address"],
                    th[_header_with_tooltip("State", "state")],
                    th[_header_with_tooltip("Stratum", "stratum")],
                    th[_header_with_tooltip("Poll", "poll")],
                    th[_header_with_tooltip("Reach", "reach")],
                    th[_header_with_tooltip("Last Rx", "last_rx")],
                    th[_header_with_tooltip("Latest Meas", "latest_meas")],
                    th[_header_with_tooltip("Meas Error", "latest_meas_err")],
                ]
            ],
            tbody[[_source_row(source) for source in sources]],
        ],
    ]


def _header_with_tooltip(text: str, tooltip_key: str) -> Element | str:
    """Create a table header with tooltip if available.

    Args:
        text: The header text to display.
        tooltip_key: Key to lookup in SOURCE_TOOLTIPS.

    Returns:
        htpy Element with tooltip or plain text.
    """
    tooltip_content = SOURCE_TOOLTIPS.get(tooltip_key)
    if tooltip_content:
        return tooltip_label(text, tooltip_content)
    return text


def _source_row(source: Source | EnrichedSource) -> Element:
    """Create a table row for a single source.

    Row styling is based on source state:
    - SELECTED (*): green highlight
    - FALSETICKER (x): red highlight
    - JITTERY (~): yellow highlight
    - unreachable: faded

    Args:
        source: Source or EnrichedSource object.

    Returns:
        htpy Element for the table row with data attributes for JS enhancement.
    """
    # Extract the raw Source if we have an EnrichedSource
    raw_source = source.source if isinstance(source, EnrichedSource) else source

    # Determine row class based on state
    row_class = _get_row_class(raw_source)

    # Format mode as badge
    mode_badge = _format_mode_badge(raw_source.mode.name)

    # Format state name (capitalize first letter)
    state_name = raw_source.state.name.replace("_", " ").title()

    # Format poll as 2^poll seconds
    poll_seconds = 2**raw_source.poll
    poll_formatted = format_duration(poll_seconds)

    # Format reachability with visual + octal
    reach_visual = _format_reach_visual(raw_source.reachability)

    # Format measurement values with direction coloring
    latest_meas_element = _format_offset_with_direction(raw_source.latest_meas)
    meas_err_formatted = format_offset(raw_source.latest_meas_err)

    # Calculate timestamps for JS real-time updates
    current_time = time.time()
    last_rx_timestamp = int(current_time - raw_source.last_sample_ago)

    # Create last-rx cell with data attributes for JS enhancement
    last_rx_cell = td(
        ".last-rx",
        **{
            "data-timestamp": str(last_rx_timestamp),
        },
    )[span(".time-since")[format_duration(int(raw_source.last_sample_ago)) + " ago"]]

    # Create poll cell with data attributes for countdown
    poll_cell = td(
        ".poll",
        **{
            "data-poll-interval": str(poll_seconds),
            "data-last-rx-time": str(last_rx_timestamp),
        },
    )[
        span(".countdown")[poll_formatted]  # Static fallback
    ]

    # Get display name from source
    if isinstance(source, EnrichedSource):
        display_name = source.display_name
        # Add country flag if available
        address_content: list[Element | str] = []
        if source.country_flag:
            address_content.append(
                span(
                    ".country-flag",
                    title=source.country_name or "",
                )[source.country_flag + " "]
            )
        address_content.append(display_name)
        address_cell = td(".address")[address_content]
    else:
        address_cell = td(".address")[raw_source.address]

    return tr(row_class)[
        td(".mode")[mode_badge],
        address_cell,
        td(".state")[state_name],
        td(".stratum")[str(raw_source.stratum)],
        poll_cell,
        td(".reach")[reach_visual],
        last_rx_cell,
        td(".latest-meas")[latest_meas_element],
        td(".meas-err")[meas_err_formatted],
    ]


def _get_row_class(source: Source) -> str:
    """Get CSS class for source row based on state.

    Args:
        source: Source object from pychrony.

    Returns:
        CSS class string for the row.
    """
    state_name = source.state.name

    # Map state names to CSS classes
    if state_name == "SELECTED":
        return ".source-row.source-selected"
    if state_name == "FALSETICKER":
        return ".source-row.source-falseticker"
    if state_name == "JITTERY":
        return ".source-row.source-jittery"
    if not source.is_reachable():
        return ".source-row.source-unreachable"

    return ".source-row"


def _format_mode_badge(mode_name: str) -> Element:
    """Create a color-coded mode badge element.

    Args:
        mode_name: Mode enum name (e.g., "CLIENT", "PEER", "LOCAL").

    Returns:
        htpy Element with styled badge and tooltip.
    """
    # Map mode names to display info
    mode_info = {
        "CLIENT": ("Srv", "Server", "server"),
        "PEER": ("Peer", "Peer", "peer"),
        "LOCAL": ("Ref", "Reference Clock", "refclock"),
    }

    short_name, full_name, css_class = mode_info.get(
        mode_name, ("?", "Unknown", "server")
    )

    return span(
        f".mode-badge.mode-badge--{css_class}",
        title=full_name,
    )[short_name]


def _format_reach_visual(reachability: int) -> Element:
    """Format reachability as visual 8-bit indicator plus octal value.

    Args:
        reachability: Reachability register value (0-255).

    Returns:
        htpy Element with visual bits, octal value, and tooltip with percentage.
    """
    bits = format_reachability_visual(reachability)
    octal = format_reachability(reachability)

    # Calculate reachability percentage
    success_count = sum(1 for bit in bits if bit)
    percentage = int(success_count / 8 * 100)
    tooltip_text = f"Reachability: {octal} ({percentage}%)"

    # Create visual bit indicator
    bit_elements = [
        span(f".reach-bit.{'success' if bit else 'failure'}") for bit in bits
    ]

    return span[
        span(".reach-visual", title=tooltip_text)[bit_elements],
        octal,
    ]


def _format_offset_with_direction(offset: float) -> Element:
    """Format offset with direction-based coloring.

    Positive offsets (local ahead) are shown in blue/cyan.
    Negative offsets (local behind) are shown in orange.

    Args:
        offset: Offset in seconds.

    Returns:
        htpy Element with colored offset value.
    """
    formatted = format_offset(offset)
    direction_class = ".offset-positive" if offset >= 0 else ".offset-negative"
    return span(direction_class)[formatted]
