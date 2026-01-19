"""Chrony service for fetching data from chronyd."""

from dataclasses import dataclass

from pychrony import (
    ChronyConnection,
    ChronyConnectionError,
    ChronyLibraryError,
    ChronyPermissionError,
    RTCData,
    Source,
    SourceStats,
    TrackingStatus,
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
        with ChronyConnection(socket_path) as conn:
            tracking = conn.get_tracking()
            sources = conn.get_sources()
            source_stats = conn.get_source_stats()
            rtc = conn.get_rtc_data()  # Returns None if unavailable
    except (ChronyConnectionError, ChronyLibraryError):
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

    return ChronyData(
        tracking=tracking,
        sources=sources,
        source_stats=source_stats,
        rtc=rtc,
        error=None,
    )
