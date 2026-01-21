"""Source statistics table component."""

from htpy import Element, div, h2, section, table, tbody, td, th, thead, tr
from pychrony import SourceStats

from second_hand.components.base import tooltip_label
from second_hand.components.tooltips import STATS_TOOLTIPS
from second_hand.utils import format_duration, format_frequency, format_offset


def stats_table(source_stats: list[SourceStats]) -> Element:
    """Create the source statistics table section.

    Displays statistical data for each source including reference ID, samples,
    runs, span, offset, standard deviation, residual frequency, skew, and offset error.
    Table headers include tooltips explaining each column.

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
                    th[_header_with_tooltip("Ref ID", "reference_id")],
                    th[_header_with_tooltip("Samples", "samples")],
                    th[_header_with_tooltip("Runs", "runs")],
                    th[_header_with_tooltip("Span", "span")],
                    th[_header_with_tooltip("Offset", "offset")],
                    th[_header_with_tooltip("Offset Err", "offset_err")],
                    th[_header_with_tooltip("Std Dev", "std_dev")],
                    th[_header_with_tooltip("Resid Freq", "resid_freq")],
                    th[_header_with_tooltip("Skew", "skew")],
                ]
            ],
            tbody[[_stats_row(stats) for stats in source_stats]],
        ],
    ]


def _header_with_tooltip(text: str, tooltip_key: str) -> Element | str:
    """Create a table header with tooltip if available.

    Args:
        text: The header text to display.
        tooltip_key: Key to lookup in STATS_TOOLTIPS.

    Returns:
        htpy Element with tooltip or plain text.
    """
    tooltip_content = STATS_TOOLTIPS.get(tooltip_key)
    if tooltip_content:
        return tooltip_label(text, tooltip_content)
    return text


def _stats_row(stats: SourceStats) -> Element:
    """Create a table row for source statistics.

    Args:
        stats: SourceStats object from pychrony.

    Returns:
        htpy Element for the table row.
    """
    # Format reference_id as hex
    ref_id_formatted = f"{stats.reference_id:08X}"

    # Format span as duration
    span_formatted = format_duration(stats.span)

    # Format std_dev in scientific notation
    std_dev_formatted = f"{stats.std_dev:.2e}"

    return tr(".stats-row")[
        td(".address")[stats.address],
        td(".ref-id")[ref_id_formatted],
        td(".samples")[str(stats.samples)],
        td(".runs")[str(stats.runs)],
        td(".span")[span_formatted],
        td(".offset")[format_offset(stats.offset)],
        td(".offset-err")[format_offset(stats.offset_err)],
        td(".std-dev")[std_dev_formatted],
        td(".resid-freq")[format_frequency(stats.resid_freq)],
        td(".skew")[format_frequency(stats.skew)],
    ]
