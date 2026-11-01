"""GeoIP service for IP address geolocation via ipwho.is.

Provides country-level geolocation using the free ipwho.is web service over
HTTPS. The service handles private IPs gracefully and caches results.
"""

import asyncio
import ipaddress
import logging
from dataclasses import dataclass

import httpx2
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# ipwho.is free tier: 1000 requests/day per client IP, no API key needed.
# HTTPS is required so on-path attackers cannot tamper with the country data
# that is rendered into the dashboard.
GEOIP_API_URL = "https://ipwho.is/{ip}?fields=success,message,country_code,country"

REQUEST_TIMEOUT_SECONDS = 3.0

# Failures expire much sooner than answers, so one dropped request does not
# hide a source's flag for long. The floor is the free tier's daily budget: a
# source that keeps failing is retried 96 times a day at this TTL, which keeps
# ten such sources under 1000 requests.
FAILURE_CACHE_TTL_SECONDS = 900

# Longest real country name is well under this; the cap only exists to bound
# what a misbehaving upstream can put into the rendered page.
MAX_COUNTRY_NAME_LENGTH = 64


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


def _clean_country_code(value: object) -> str | None:
    """Validate an upstream country code, returning None if implausible.

    HTTPS authenticates the transport, but the payload is still third-party
    data that ends up in the rendered dashboard. Accept only ISO 3166-1
    alpha-2 shaped values so a misbehaving upstream cannot inject arbitrary
    strings.

    Args:
        value: Raw ``country_code`` field from the API response.

    Returns:
        The upper-cased two-letter code, or None if it is not alpha-2 shaped.
    """
    if not isinstance(value, str):
        return None
    code = value.strip().upper()
    if len(code) != 2 or not code.isascii() or not code.isalpha():
        return None
    return code


def _clean_country_name(value: object) -> str | None:
    """Validate an upstream country name, returning None if implausible.

    Args:
        value: Raw ``country`` field from the API response.

    Returns:
        The stripped name, or None if it is empty or implausibly long.
    """
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name or len(name) > MAX_COUNTRY_NAME_LENGTH:
        return None
    return name


class GeoIPService:
    """Look up IP address geolocation via ipwho.is.

    One instance lives for the life of the application, created in its
    lifespan around a shared HTTP client so connections are pooled across
    lookups. Answers are cached to stay inside the 1000 requests/day limit.

    Attributes:
        failure_count: Number of lookups that failed (FR-024).
    """

    def __init__(
        self,
        client: httpx2.AsyncClient,
        *,
        cache_ttl: int = 3600,
        failure_ttl: int = FAILURE_CACHE_TTL_SECONDS,
        cache_maxsize: int = 1024,
    ) -> None:
        """Initialize the GeoIP service.

        Args:
            client: HTTP client used for every request; the caller owns and
                closes it.
            cache_ttl: How long an answer is cached, in seconds.
            failure_ttl: How long a failed lookup is cached, in seconds.
            cache_maxsize: Maximum entries in each of the two caches.
        """
        self._client = client
        self._cache: TTLCache[str, GeoIPResult] = TTLCache(
            maxsize=cache_maxsize, ttl=cache_ttl
        )
        self._failures: TTLCache[str, GeoIPResult] = TTLCache(
            maxsize=cache_maxsize, ttl=failure_ttl
        )
        self.failure_count = 0

    async def lookup(self, ip: str) -> GeoIPResult:
        """Look up the country for an IP address.

        Args:
            ip: IP address string (IPv4 or IPv6).

        Returns:
            GeoIPResult with country information, or empty result for
            private/local IPs or lookup failures.
        """
        cached = self._cache.get(ip) or self._failures.get(ip)
        if cached is not None:
            return cached

        if self._is_private_ip(ip):
            result = GeoIPResult(
                ip_address=ip, is_private=True, country_code=None, country_name=None
            )
            self._cache[ip] = result
            return result

        result = await self._fetch(ip)
        if result is None:
            self.failure_count += 1
            result = GeoIPResult(
                ip_address=ip, is_private=False, country_code=None, country_name=None
            )
            self._failures[ip] = result
        else:
            self._cache[ip] = result
        return result

    async def _fetch(self, ip: str) -> GeoIPResult | None:
        """Query ipwho.is for one public address.

        Returns:
            The parsed result, or None if the lookup failed for any reason.
        """
        # httpx2's own timeout limits each phase (connect, read, ...) on its
        # own; this caps the whole request so a slow upstream cannot hold the
        # page render past it.
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                response = await self._client.get(GEOIP_API_URL.format(ip=ip))
        except (TimeoutError, httpx2.TimeoutException):
            logger.debug("GeoIP lookup timed out for %s", ip)
            return None
        # Flags are decoration: no failure here may take the dashboard down.
        except Exception as e:
            logger.debug("GeoIP lookup failed for %s: %s", ip, e)
            return None

        if response.status_code != 200:
            logger.debug(
                "GeoIP API returned status %d for %s", response.status_code, ip
            )
            return None

        try:
            data = response.json()
        except ValueError as e:
            logger.debug("GeoIP API returned invalid JSON for %s: %s", ip, e)
            return None

        if not isinstance(data, dict) or not data.get("success"):
            message = data.get("message") if isinstance(data, dict) else None
            logger.debug("GeoIP lookup failed for %s: %s", ip, message)
            return None

        return GeoIPResult(
            ip_address=ip,
            is_private=False,
            country_code=_clean_country_code(data.get("country_code")),
            country_name=_clean_country_name(data.get("country")),
        )

    async def batch_lookup(self, ips: list[str]) -> dict[str, GeoIPResult]:
        """Look up countries for multiple IP addresses concurrently.

        Duplicates are looked up once: concurrent lookups of the same address
        would all miss the cache and each spend a request.

        Args:
            ips: List of IP address strings.

        Returns:
            Dictionary mapping IP addresses to GeoIPResult objects.
        """
        async with asyncio.TaskGroup() as tg:
            tasks = {ip: tg.create_task(self.lookup(ip)) for ip in dict.fromkeys(ips)}
        return {ip: task.result() for ip, task in tasks.items()}

    def _is_private_ip(self, ip_str: str) -> bool:
        """Check if an IP address is private/local/reserved.

        ``is_global`` also rules out shared address space (100.64.0.0/10,
        used by carrier-grade NAT and Tailscale), which ``is_private`` does
        not cover and ipwho.is can only answer with "Reserved range".
        Reserved and multicast ranges are checked separately because some of
        them still count as global.

        Args:
            ip_str: IP address string.

        Returns:
            True if the IP is not globally routable, reserved, or multicast.
        """
        try:
            ip = ipaddress.ip_address(ip_str)
            return not ip.is_global or ip.is_reserved or ip.is_multicast
        except ValueError:
            # Invalid IP treated as non-geolocatable
            return True

    @property
    def cache_size(self) -> int:
        """Current number of cached answers and failures."""
        return len(self._cache) + len(self._failures)
