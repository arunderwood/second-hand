"""RTC (Real-Time Clock) section component."""

from htpy import Element, div, h2, p, section
from pychrony import RTCData


def rtc_section(rtc: RTCData | None) -> Element:
    """Create the RTC data display section.

    Displays RTC offset, drift rate, and calibration samples,
    or a message indicating RTC is not configured.

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

    # Format offset with sign
    offset_formatted = f"{rtc.offset:+.6f} s"

    # Format drift in ppm
    drift_formatted = f"{rtc.freq_offset:+.3f} ppm"

    return section(".rtc-section")[
        h2(".section-title")["Hardware RTC"],
        div(".rtc-stats")[
            _rtc_stat("Offset", offset_formatted),
            _rtc_stat("Drift", drift_formatted),
            _rtc_stat("Samples", str(rtc.samples)),
        ],
    ]


def _rtc_stat(title: str, value: str) -> Element:
    """Create a single RTC statistic display.

    Args:
        title: The label for the stat.
        value: The value to display.

    Returns:
        htpy Element for the RTC stat.
    """
    return div(".rtc-stat")[
        div(".rtc-stat-title")[title],
        div(".rtc-stat-value")[value],
    ]
