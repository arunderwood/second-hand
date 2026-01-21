"""Chrony service for fetching data from chronyd."""

from dataclasses import dataclass, field

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

from second_hand.utils import country_code_to_flag


@dataclass
class EnrichedSource:
    """An NTP source with additional display metadata.

    Wraps the pychrony Source object with resolved hostname and geolocation
    information for enhanced dashboard display.

    Attributes:
        source: Original Source data from chronyd.
        hostname: Resolved hostname via reverse DNS, or None if unavailable.
        country_code: ISO 3166-1 alpha-2 country code, or None if unavailable.
        country_name: Full country name for tooltip, or None if unavailable.
        country_flag: Flag emoji from country_code, or empty string.
    """

    source: Source
    hostname: str | None = None
    country_code: str | None = None
    country_name: str | None = None
    country_flag: str = field(default="")

    def __post_init__(self) -> None:
        """Derive country_flag from country_code if not set."""
        if not self.country_flag and self.country_code:
            self.country_flag = country_code_to_flag(self.country_code)

    @property
    def display_name(self) -> str:
        """Get display name in 'hostname (IP)' or just IP format.

        Returns:
            'hostname (IP)' if hostname is available, otherwise just the IP.
        """
        if self.hostname:
            return f"{self.hostname} ({self.source.address})"
        return self.source.address


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


async def enrich_sources(sources: list[Source]) -> list[EnrichedSource]:
    """Enrich NTP sources with hostname and geolocation data.

    Performs batch DNS lookups and GeoIP lookups for all sources,
    then combines the results into EnrichedSource objects.

    Args:
        sources: List of Source objects from pychrony.

    Returns:
        List of EnrichedSource objects with display metadata.
    """
    from second_hand.services.dns import DNSService
    from second_hand.services.geoip import GeoIPService

    # Get service instances
    dns_service = DNSService.get_instance()
    geoip_service = GeoIPService.get_instance()

    # Extract IP addresses for batch lookup
    ips = [source.address for source in sources]

    # Perform batch DNS and GeoIP lookups
    hostnames = await dns_service.batch_reverse_lookup(ips)
    geo_results = await geoip_service.batch_lookup(ips)

    # Build enriched sources
    enriched: list[EnrichedSource] = []
    for source in sources:
        ip = source.address
        hostname = hostnames.get(ip)
        geo_result = geo_results.get(ip)

        enriched.append(
            EnrichedSource(
                source=source,
                hostname=hostname,
                country_code=geo_result.country_code if geo_result else None,
                country_name=geo_result.country_name if geo_result else None,
                country_flag=country_code_to_flag(
                    geo_result.country_code if geo_result else None
                ),
            )
        )

    return enriched
