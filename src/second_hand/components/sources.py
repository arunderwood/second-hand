"""Sources table component for displaying NTP sources."""

from htpy import Element, div, h2, section, table, tbody, td, th, thead, tr
from pychrony import Source

from second_hand.utils import format_duration, format_reachability


def sources_table(sources: list[Source]) -> Element:
    """Create the NTP sources table section.

    Displays all configured NTP sources with address, state, stratum,
    poll interval, reachability, and last sample time.

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
                    th["Address"],
                    th["State"],
                    th["Stratum"],
                    th["Poll"],
                    th["Reach"],
                    th["Last Rx"],
                ]
            ],
            tbody[[_source_row(source) for source in sources]],
        ],
    ]


def _source_row(source: Source) -> Element:
    """Create a table row for a single source.

    Args:
        source: Source object from pychrony.

    Returns:
        htpy Element for the table row.
    """
    # Determine row class based on state
    row_class = ".source-row"
    if source.is_selected():
        row_class += ".selected"
    elif not source.is_reachable():
        row_class += ".unreachable"

    # Format state name (capitalize first letter)
    state_name = source.state.name.replace("_", " ").title()

    # Format poll as 2^poll seconds
    poll_seconds = 2**source.poll
    poll_formatted = format_duration(poll_seconds)

    return tr(row_class)[
        td(".address")[source.address],
        td(".state")[state_name],
        td(".stratum")[str(source.stratum)],
        td(".poll")[poll_formatted],
        td(".reach")[format_reachability(source.reachability)],
        td(".last-rx")[format_duration(source.last_sample_ago)],
    ]
