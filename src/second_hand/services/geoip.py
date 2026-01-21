"""GeoIP service for IP address geolocation via ip-api.com.

Provides country-level geolocation using the free ip-api.com web service.
The service handles private IPs gracefully and caches results.
"""

import ipaddress
import logging
from dataclasses import dataclass
from typing import ClassVar

import aiohttp
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# ip-api.com free tier: 45 requests/minute, no API key needed
GEOIP_API_URL = "http://ip-api.com/json/{ip}?fields=status,countryCode,country"


@dataclass
class GeoIPResult:
    """Result of a GeoIP lookup.

    Attributes:
        ip_address: The IP address that was looked up.
        is_private: True if the IP is private/local/reserved.
        country_code: ISO 3166-1 alpha-2 country code, or None if not found.
        country_name: Full country name in English, or None if not found.
    """

    ip_address: str
    is_private: bool
    country_code: str | None
    country_name: str | None


class GeoIPService:
    """Service for looking up IP address geolocation via ip-api.com.

    Uses the free ip-api.com API for country-level lookups.
    Implements singleton pattern for application lifecycle management.
    Results are cached to minimize API calls (45 req/min limit).

    Attributes:
        failure_count: Counter for tracking GeoIP lookup failures (FR-024).
    """

    _instance: ClassVar["GeoIPService | None"] = None
    failure_count: int = 0

    def __init__(self, cache_ttl: int = 3600, cache_maxsize: int = 1024) -> None:
        """Initialize the GeoIP service.

        Args:
            cache_ttl: Cache TTL in seconds (default: 1 hour).
            cache_maxsize: Maximum cache entries (default: 1024).
        """
        self._cache: TTLCache[str, GeoIPResult] = TTLCache(
            maxsize=cache_maxsize, ttl=cache_ttl
        )

    async def lookup(self, ip: str) -> GeoIPResult:
        """Look up the country for an IP address.

        Args:
            ip: IP address string (IPv4 or IPv6).

        Returns:
            GeoIPResult with country information, or empty result for
            private/local IPs or lookup failures.
        """
        # Check cache first
        if ip in self._cache:
            return self._cache[ip]

        # Check for private/local IPs
        if self._is_private_ip(ip):
            result = GeoIPResult(
                ip_address=ip,
                is_private=True,
                country_code=None,
                country_name=None,
            )
            self._cache[ip] = result
            return result

        # Query the API
        try:
            async with aiohttp.ClientSession() as session, session.get(
                GEOIP_API_URL.format(ip=ip), timeout=aiohttp.ClientTimeout(total=3)
            ) as response:
                if response.status != 200:
                    logger.debug(
                        "GeoIP API returned status %d for %s", response.status, ip
                    )
                    self.failure_count += 1
                    result = GeoIPResult(
                        ip_address=ip,
                        is_private=False,
                        country_code=None,
                        country_name=None,
                    )
                    self._cache[ip] = result
                    return result

                data = await response.json()

                if data.get("status") != "success":
                    logger.debug(
                        "GeoIP lookup failed for %s: %s", ip, data.get("message")
                    )
                    self.failure_count += 1
                    result = GeoIPResult(
                        ip_address=ip,
                        is_private=False,
                        country_code=None,
                        country_name=None,
                    )
                    self._cache[ip] = result
                    return result

                result = GeoIPResult(
                    ip_address=ip,
                    is_private=False,
                    country_code=data.get("countryCode"),
                    country_name=data.get("country"),
                )
                self._cache[ip] = result
                return result

        except TimeoutError:
            logger.debug("GeoIP lookup timed out for %s", ip)
            self.failure_count += 1
        except Exception as e:
            logger.debug("GeoIP lookup failed for %s: %s", ip, e)
            self.failure_count += 1

        result = GeoIPResult(
            ip_address=ip,
            is_private=False,
            country_code=None,
            country_name=None,
        )
        self._cache[ip] = result
        return result

    async def batch_lookup(self, ips: list[str]) -> dict[str, GeoIPResult]:
        """Look up countries for multiple IP addresses.

        Args:
            ips: List of IP address strings.

        Returns:
            Dictionary mapping IP addresses to GeoIPResult objects.
        """
        results = {}
        for ip in ips:
            results[ip] = await self.lookup(ip)
        return results

    def _is_private_ip(self, ip_str: str) -> bool:
        """Check if an IP address is private/local/reserved.

        Args:
            ip_str: IP address string.

        Returns:
            True if the IP is private, loopback, link-local, or reserved.
        """
        try:
            ip = ipaddress.ip_address(ip_str)
            return (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            )
        except ValueError:
            # Invalid IP treated as non-geolocatable
            return True

    @property
    def is_available(self) -> bool:
        """Check if the GeoIP service is available."""
        return True  # API is always available (may be rate-limited)

    @property
    def cache_size(self) -> int:
        """Current number of entries in the cache."""
        return len(self._cache)

    @classmethod
    def get_instance(cls) -> "GeoIPService":
        """Get the singleton instance of GeoIPService.

        Returns:
            The singleton GeoIPService instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for testing)."""
        cls._instance = None
