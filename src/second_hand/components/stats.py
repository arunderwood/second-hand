"""Source statistics table component."""

from htpy import Element, div, h2, section, table, tbody, td, th, thead, tr
from pychrony import SourceStats

from second_hand.utils import format_offset


def stats_table(source_stats: list[SourceStats]) -> Element:
    """Create the source statistics table section.

    Displays statistical data for each source including samples,
    offset, standard deviation, and skew.

    Args:
        source_stats: List of SourceStats objects from pychrony.

    Returns:
        htpy Element containing the source stats table section.
    """
    if not source_stats:
        return section(".stats-section")[
            h2(".section-title")["Source Statistics"],
            div(".empty-message")["No statistics available"],
        ]

    return section(".stats-section")[
        h2(".section-title")["Source Statistics"],
        table(".data-table")[
            thead[
                tr[
                    th["Address"],
                    th["Samples"],
                    th["Offset"],
                    th["Std Dev"],
                    th["Skew"],
                ]
            ],
            tbody[[_stats_row(stats) for stats in source_stats]],
        ],
    ]


def _stats_row(stats: SourceStats) -> Element:
    """Create a table row for source statistics.

    Args:
        stats: SourceStats object from pychrony.

    Returns:
        htpy Element for the table row.
    """
    # Format std_dev in scientific notation
    std_dev_formatted = f"{stats.std_dev:.2e}"

    # Format skew in ppm
    skew_formatted = f"{stats.skew:.3f} ppm"

    return tr(".stats-row")[
        td(".address")[stats.address],
        td(".samples")[str(stats.samples)],
        td(".offset")[format_offset(stats.offset)],
        td(".std-dev")[std_dev_formatted],
        td(".skew")[skew_formatted],
    ]
