"""Tracking section component for chrony status display."""

from htpy import Element, div, h2, section

from second_hand.services.chrony import ChronyData
from second_hand.utils import format_offset


def tracking_section(data: ChronyData) -> Element:
    """Create the tracking status section with stat boxes.

    Displays high-value metrics: sync status, offset, stratum, and reference source.

    Args:
        data: Aggregated chrony data from the service layer.

    Returns:
        htpy Element containing the tracking status section.
    """
    if data.tracking is None:
        # No tracking data - show placeholder
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

    # Determine sync status
    if tracking.is_synchronized():
        sync_status = "Synchronized"
        sync_status_class = "success"
    else:
        sync_status = "Not Synchronized"
        sync_status_class = "warning"

    # Format offset
    offset_formatted = format_offset(tracking.offset)

    # Get reference source name
    reference = tracking.reference_id_name if tracking.reference_id_name else "None"

    return section(".tracking-section")[
        h2(".section-title")["Time Synchronization"],
        div(".stats-grid")[
            _stat_box("Status", sync_status, status=sync_status_class),
            _stat_box("Offset", offset_formatted),
            _stat_box("Stratum", str(tracking.stratum)),
            _stat_box("Reference", reference),
        ],
    ]


def _stat_box(title: str, value: str, status: str = "") -> Element:
    """Create a single statistic display box.

    Args:
        title: The label for the stat.
        value: The value to display.
        status: Optional status class (success, warning, error).

    Returns:
        htpy Element for the stat box.
    """
    classes = ".stat-box"
    attrs: dict[str, str] = {}
    if status:
        attrs["data-status"] = status

    return div(classes, attrs)[
        div(".stat-title")[title],
        div(".stat-value")[value],
    ]
