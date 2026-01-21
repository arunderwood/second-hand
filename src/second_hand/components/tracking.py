"""Tracking section component for chrony status display."""

from htpy import Element, div, h2, section, span

from second_hand.components.base import tooltip_label
from second_hand.components.tooltips import TRACKING_TOOLTIPS
from second_hand.services.chrony import ChronyData
from second_hand.utils import (
    format_duration,
    format_frequency,
    format_offset,
    format_timestamp,
    get_health_status,
)


def tracking_section(data: ChronyData) -> Element:
    """Create the tracking status section with compact stat boxes.

    Displays all TrackingStatus fields in a dense grid layout. All labels have
    tooltips and values have health-based coloring where applicable.

    Args:
        data: Aggregated chrony data from the service layer.

    Returns:
        htpy Element containing the tracking status section.
    """
    if data.tracking is None:
        return section(".tracking-section")[
            h2(".section-title")["Time Synchronization"],
            div(".stats-grid")[
                _stat_box("Status", "Unknown", status="error"),
                _stat_box("Offset", "N/A"),
                _stat_box("Stratum", "N/A"),
                _stat_box("Reference", "N/A"),
            ],
        ]

    tracking = data.tracking

    # Sync status
    if tracking.is_synchronized():
        sync_status = "Synchronized"
        sync_status_class = "success"
    else:
        sync_status = "Not Sync"
        sync_status_class = "error"

    # Reference info
    reference = tracking.reference_id_name if tracking.reference_id_name else "None"
    reference_ip = tracking.reference_ip if tracking.reference_ip else "N/A"

    # Leap status
    leap_status_name = tracking.leap_status.name.replace("_", " ").title()
    leap_health = _get_leap_health(tracking.leap_status.name)

    # All stats in a single dense grid
    return section(".tracking-section")[
        h2(".section-title")["Time Synchronization"],
        div(".stats-grid")[
            # Row 1: Primary status
            _stat_box_with_tooltip(
                "Status", sync_status, "leap_status", status=sync_status_class
            ),
            _stat_box_with_tooltip_and_health(
                "Offset",
                format_offset(tracking.offset),
                "offset",
                get_health_status("offset", tracking.offset),
            ),
            _stat_box_with_tooltip_and_health(
                "Stratum",
                str(tracking.stratum),
                "stratum",
                get_health_status("stratum", tracking.stratum),
            ),
            _stat_box_with_tooltip("Reference", reference, "reference"),
            _stat_box_with_tooltip("Ref IP", reference_ip, "reference_ip"),
            _stat_box_with_tooltip_and_health(
                "Leap", leap_status_name, "leap_status", leap_health
            ),
            _stat_box_with_tooltip(
                "Ref Time", format_timestamp(tracking.ref_time), "ref_time"
            ),
            _stat_box_with_tooltip(
                "Interval",
                format_duration(int(tracking.update_interval)),
                "update_interval",
            ),
            # Row 2: Offset metrics
            _stat_box_with_tooltip_and_health(
                "Last Offset",
                format_offset(tracking.last_offset),
                "last_offset",
                get_health_status("offset", tracking.last_offset),
            ),
            _stat_box_with_tooltip_and_health(
                "RMS Offset",
                format_offset(tracking.rms_offset),
                "rms_offset",
                get_health_status("rms_offset", tracking.rms_offset),
            ),
            _stat_box_with_tooltip_and_health(
                "Root Delay",
                format_offset(tracking.root_delay),
                "root_delay",
                get_health_status("root_delay", tracking.root_delay),
            ),
            _stat_box_with_tooltip_and_health(
                "Root Disp",
                format_offset(tracking.root_dispersion),
                "root_dispersion",
                get_health_status("root_dispersion", tracking.root_dispersion),
            ),
            # Row 3: Frequency metrics
            _stat_box_with_tooltip_and_health(
                "Frequency",
                format_frequency(tracking.frequency),
                "frequency",
                get_health_status("frequency", tracking.frequency),
            ),
            _stat_box_with_tooltip(
                "Resid Freq",
                format_frequency(tracking.residual_freq),
                "residual_freq",
            ),
            _stat_box_with_tooltip_and_health(
                "Skew",
                format_frequency(tracking.skew),
                "skew",
                get_health_status("skew", tracking.skew),
            ),
        ],
    ]


def _get_leap_health(leap_status_name: str) -> str:
    """Get health status for leap status."""
    if leap_status_name == "NORMAL":
        return "healthy"
    if leap_status_name == "NOT_SYNCHRONISED":
        return "error"
    return "warning"


def _stat_box(title: str, value: str, status: str = "") -> Element:
    """Create a single statistic display box without tooltip."""
    attrs: dict[str, str] = {}
    if status:
        attrs["data-status"] = status

    return div(".stat-box", attrs)[
        div(".stat-title")[title],
        div(".stat-value")[value],
    ]


def _stat_box_with_tooltip(
    title: str, value: str, tooltip_key: str, status: str = ""
) -> Element:
    """Create a single statistic display box with tooltip."""
    attrs: dict[str, str] = {}
    if status:
        attrs["data-status"] = status

    tooltip_content = TRACKING_TOOLTIPS.get(tooltip_key)
    title_element: Element | str = (
        tooltip_label(title, tooltip_content) if tooltip_content else title
    )

    return div(".stat-box", attrs)[
        div(".stat-title")[title_element],
        div(".stat-value")[value],
    ]


def _stat_box_with_tooltip_and_health(
    title: str, value: str, tooltip_key: str, health_status: str
) -> Element:
    """Create a statistic display box with tooltip and health-colored value."""
    tooltip_content = TRACKING_TOOLTIPS.get(tooltip_key)
    title_element: Element | str = (
        tooltip_label(title, tooltip_content) if tooltip_content else title
    )

    value_element = span(f".status-{health_status}")[value]

    return div(".stat-box")[
        div(".stat-title")[title_element],
        div(".stat-value")[value_element],
    ]
