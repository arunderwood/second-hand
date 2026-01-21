"""Sources table component for displaying NTP sources."""

from htpy import Element, div, h2, section, span, table, tbody, td, th, thead, tr
from pychrony import Source

from second_hand.components.base import tooltip_label
from second_hand.components.tooltips import SOURCE_TOOLTIPS
from second_hand.utils import (
    format_duration,
    format_offset,
    format_reachability,
    format_reachability_visual,
)


def sources_table(sources: list[Source]) -> Element:
    """Create the NTP sources table section.

    Displays all configured NTP sources with mode, address, state, stratum,
    poll interval, reachability, last sample time, and measurement data.
    Table headers include tooltips explaining each column.
    Rows are styled based on source state (selected, falseticker, unreachable, jittery).

    Args:
        sources: List of Source objects from pychrony.

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


def _source_row(source: Source) -> Element:
    """Create a table row for a single source.

    Row styling is based on source state:
    - SELECTED (*): green highlight
    - FALSETICKER (x): red highlight
    - JITTERY (~): yellow highlight
    - unreachable: faded

    Args:
        source: Source object from pychrony.

    Returns:
        htpy Element for the table row.
    """
    # Determine row class based on state
    row_class = _get_row_class(source)

    # Format mode symbol
    mode_symbol = _format_mode_symbol(source.mode.name)

    # Format state name (capitalize first letter)
    state_name = source.state.name.replace("_", " ").title()

    # Format poll as 2^poll seconds
    poll_seconds = 2**source.poll
    poll_formatted = format_duration(poll_seconds)

    # Format reachability with visual + octal
    reach_visual = _format_reach_visual(source.reachability)

    # Format measurement values with direction coloring
    latest_meas_element = _format_offset_with_direction(source.latest_meas)
    meas_err_formatted = format_offset(source.latest_meas_err)

    return tr(row_class)[
        td(".mode")[mode_symbol],
        td(".address")[source.address],
        td(".state")[state_name],
        td(".stratum")[str(source.stratum)],
        td(".poll")[poll_formatted],
        td(".reach")[reach_visual],
        td(".last-rx")[format_duration(source.last_sample_ago)],
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


def _format_mode_symbol(mode_name: str) -> str:
    """Convert mode name to display symbol.

    Args:
        mode_name: Mode enum name (e.g., "CLIENT", "PEER", "LOCAL").

    Returns:
        Symbol character for display: ^ (client), = (peer), # (local).
    """
    mode_symbols = {
        "CLIENT": "^",
        "PEER": "=",
        "LOCAL": "#",
    }
    return mode_symbols.get(mode_name, "?")


def _format_reach_visual(reachability: int) -> Element:
    """Format reachability as visual 8-bit indicator plus octal value.

    Args:
        reachability: Reachability register value (0-255).

    Returns:
        htpy Element with visual bits and octal value.
    """
    bits = format_reachability_visual(reachability)
    octal = format_reachability(reachability)

    # Create visual bit indicator
    bit_elements = [
        span(f".reach-bit.{'success' if bit else 'failure'}") for bit in bits
    ]

    return span[
        span(".reach-visual")[bit_elements],
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
