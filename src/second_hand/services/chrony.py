"""Chrony service for fetching data from chronyd."""

import asyncio
import logging
from dataclasses import dataclass, field

from pychrony import (
    ChronyConnection,
    ChronyConnectionError,
    ChronyDataError,
    ChronyLibraryError,
    ChronyPermissionError,
    RTCData,
    Source,
    SourceStats,
    TrackingStatus,
)

from second_hand.config import get_settings
from second_hand.services.geoip import GeoIPService
from second_hand.services.rdns import ReverseDNSService
from second_hand.utils import country_code_to_flag

logger = logging.getLogger(__name__)

# The dashboard and /api/sources both fetch on every refresh, so a lasting RTC
# fault would log once per refresh per open tab. Only a new error is a warning.
_last_rtc_error: str | None = None


@dataclass
class EnrichedSource:
    """An NTP source with additional display metadata.

    Wraps the pychrony Source object with geolocation and hostname
    information for enhanced dashboard display.

    Attributes:
        source: Original Source data from chronyd.
        country_code: ISO 3166-1 alpha-2 country code, or None if unavailable.
        country_name: Full country name for tooltip, or None if unavailable.
        country_flag: Flag emoji from country_code, or empty string.
        hostname: Name from the address's PTR record, or None if it has none.
    """

    source: Source
    country_code: str | None = None
    country_name: str | None = None
    country_flag: str = field(default="")
    hostname: str | None = None

    def __post_init__(self) -> None:
        """Derive country_flag from country_code if not set."""
        if not self.country_flag and self.country_code:
            self.country_flag = country_code_to_flag(self.country_code)

    @property
    def display_name(self) -> str:
        """Get display name for the source.

        Returns:
            The resolved hostname, falling back to the address itself. A
            refclock has no address to resolve, so it shows its reference
            name ("PPS", "NMEA") either way.
        """
        return self.hostname or self.source.address


@dataclass
class ChronyData:
    """Container for all chrony data fetched for dashboard display."""

    tracking: TrackingStatus | None
    sources: list[Source]
    source_stats: list[SourceStats]
    rtc: RTCData | None
    error: str | None
    # Why chronyd gave no RTC data although it is reachable. None with rtc
    # None means chronyd tracks no RTC.
    rtc_error: str | None = None

    @property
    def is_connected(self) -> bool:
        """Check if successfully connected to chronyd."""
        return self.error is None and self.tracking is not None

    @property
    def is_synchronized(self) -> bool:
        """Check if system is synchronized."""
        return self.tracking is not None and self.tracking.is_synchronized()


def fetch_chrony_data(address: str | None = None) -> ChronyData:
    """Fetch all chrony data from chronyd.

    This blocks on chronyd's socket, so async callers must run it in a worker
    thread (``asyncio.to_thread``) rather than on the event loop.

    Args:
        address: chronyd address as "host", "host:port", or a Unix socket path.
            Defaults to the configured SECOND_HAND_CHRONY_ADDRESS.

    Returns:
        ChronyData with all available data and any error message.
    """
    # Always pass an explicit address; auto-detect can settle on an unreachable
    # Unix socket without falling back to the command port.
    if address is None:
        address = get_settings().chrony_address

    try:
        with ChronyConnection(address) as conn:
            tracking = conn.get_tracking()
            sources = conn.get_sources()
            source_stats = conn.get_source_stats()
            # A rejected or malformed RTC reply only costs the RTC panel, not
            # the rest of the dashboard.
            rtc_error = None
            try:
                rtc = conn.get_rtc_data()
            except ChronyDataError as e:
                rtc = None
                rtc_error = str(e)
            _log_rtc_error(rtc_error)
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
            error=(
                f"Permission denied connecting to chronyd at {address}. "
                "Check that chronyd's command port is reachable."
            ),
        )

    return ChronyData(
        tracking=tracking,
        sources=sources,
        source_stats=source_stats,
        rtc=rtc,
        error=None,
        rtc_error=rtc_error,
    )


def _log_rtc_error(error: str | None) -> None:
    """Warn about an RTC error unless the previous fetch already reported it."""
    global _last_rtc_error
    if error is not None:
        if error == _last_rtc_error:
            logger.debug("chronyd RTC data still unavailable: %s", error)
        else:
            logger.warning("chronyd RTC data unavailable: %s", error)
    _last_rtc_error = error


async def enrich_sources(
    sources: list[Source],
    geoip_service: GeoIPService,
    rdns_service: ReverseDNSService,
) -> list[EnrichedSource]:
    """Enrich NTP sources with geolocation and hostname data.

    Performs batch GeoIP and reverse DNS lookups for all sources and combines
    the results into EnrichedSource objects.

    Args:
        sources: List of Source objects from pychrony.
        geoip_service: The application's GeoIP service.
        rdns_service: The application's reverse DNS service.

    Returns:
        List of EnrichedSource objects with display metadata.
    """
    # Extract IP addresses for batch lookup
    ips = [source.address for source in sources]

    # Both batches at once, so a render waits on the slower lookup rather than
    # on their sum.
    async with asyncio.TaskGroup() as tg:
        geo_task = tg.create_task(geoip_service.batch_lookup(ips))
        rdns_task = tg.create_task(rdns_service.batch_lookup(ips))
    geo_results = geo_task.result()
    rdns_results = rdns_task.result()

    # Build enriched sources
    enriched: list[EnrichedSource] = []
    for source in sources:
        ip = source.address
        geo_result = geo_results.get(ip)
        rdns_result = rdns_results.get(ip)

        enriched.append(
            EnrichedSource(
                source=source,
                country_code=geo_result.country_code if geo_result else None,
                country_name=geo_result.country_name if geo_result else None,
                country_flag=country_code_to_flag(
                    geo_result.country_code if geo_result else None
                ),
                hostname=rdns_result.hostname if rdns_result else None,
            )
        )

    return enriched
