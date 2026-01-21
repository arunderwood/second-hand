"""RTC (Real-Time Clock) section component."""

from htpy import Element, div, h2, p, section
from pychrony import RTCData

from second_hand.components.base import tooltip_label
from second_hand.components.tooltips import RTC_TOOLTIPS
from second_hand.utils import (
    format_duration,
    format_frequency,
    format_offset,
    format_timestamp,
)


def rtc_section(rtc: RTCData | None) -> Element:
    """Create the RTC data display section.

    Displays all RTCData fields: ref_time, samples, runs, span, offset, and freq_offset,
    or a message indicating RTC is not configured. All labels have tooltips.

    Args:
        rtc: RTCData object from pychrony, or None if unavailable.

    Returns:
        htpy Element containing the RTC section.
    """
    if rtc is None:
        return section(".rtc-section")[
            h2(".section-title")["Hardware RTC"],
            div(".rtc-unavailable")[
                p(".unavailable-message")["RTC tracking not configured"],
            ],
        ]

    return section(".rtc-section")[
        h2(".section-title")["Hardware RTC"],
        div(".rtc-stats")[
            _rtc_stat_with_tooltip(
                "Ref Time", format_timestamp(rtc.ref_time), "ref_time"
            ),
            _rtc_stat_with_tooltip("Samples", str(rtc.samples), "samples"),
            _rtc_stat_with_tooltip("Runs", str(rtc.runs), "runs"),
            _rtc_stat_with_tooltip("Span", format_duration(rtc.span), "span"),
            _rtc_stat_with_tooltip("Offset", format_offset(rtc.offset), "offset"),
            _rtc_stat_with_tooltip(
                "Drift Rate", format_frequency(rtc.freq_offset), "drift_rate"
            ),
        ],
    ]


def _rtc_stat_with_tooltip(title: str, value: str, tooltip_key: str) -> Element:
    """Create a single RTC statistic display with tooltip.

    Args:
        title: The label for the stat.
        value: The value to display.
        tooltip_key: Key to lookup in RTC_TOOLTIPS.

    Returns:
        htpy Element for the RTC stat with tooltip on title.
    """
    tooltip_content = RTC_TOOLTIPS.get(tooltip_key)
    title_element: Element | str = (
        tooltip_label(title, tooltip_content) if tooltip_content else title
    )

    return div(".rtc-stat")[
        div(".rtc-stat-title")[title_element],
        div(".rtc-stat-value")[value],
    ]
