"""Chrony service for fetching data from chronyd."""

import contextlib
from dataclasses import dataclass

from pychrony import (
    ChronyConnectionError,
    ChronyDataError,
    ChronyLibraryError,
    ChronyPermissionError,
    RTCData,
    Source,
    SourceStats,
    TrackingStatus,
    get_rtc_data,
    get_source_stats,
    get_sources,
    get_tracking,
)


@dataclass
class ChronyData:
    """Container for all chrony data fetched for dashboard display."""

    tracking: TrackingStatus | None
    sources: list[Source]
    source_stats: list[SourceStats]
    rtc: RTCData | None
    error: str | None

    @property
    def is_connected(self) -> bool:
        """Check if successfully connected to chronyd."""
        return self.error is None and self.tracking is not None

    @property
    def is_synchronized(self) -> bool:
        """Check if system is synchronized."""
        return self.tracking is not None and self.tracking.is_synchronized()


def fetch_chrony_data(socket_path: str | None = None) -> ChronyData:
    """Fetch all chrony data from chronyd.

    Args:
        socket_path: Optional custom socket path. Uses pychrony default if None.

    Returns:
        ChronyData with all available data and any error message.
    """
    try:
        tracking = get_tracking(socket_path=socket_path)
        sources = get_sources(socket_path=socket_path)
        source_stats = get_source_stats(socket_path=socket_path)
    except ChronyConnectionError:
        return ChronyData(
            tracking=None,
            sources=[],
            source_stats=[],
            rtc=None,
            error="Unable to connect to chronyd. Is the service running?",
        )
    except ChronyPermissionError:
        return ChronyData(
            tracking=None,
            sources=[],
            source_stats=[],
            rtc=None,
            error="Permission denied. Add your user to the chrony group.",
        )
    except ChronyLibraryError:
        return ChronyData(
            tracking=None,
            sources=[],
            source_stats=[],
            rtc=None,
            error="pychrony library error. Check installation.",
        )

    # RTC is optional - not an error if unavailable
    rtc: RTCData | None = None
    with contextlib.suppress(ChronyDataError):
        rtc = get_rtc_data(socket_path=socket_path)

    return ChronyData(
        tracking=tracking,
        sources=sources,
        source_stats=source_stats,
        rtc=rtc,
        error=None,
    )
