"""DNS service for reverse hostname resolution.

Provides async reverse DNS lookups with caching using aiodns and cachetools.
The service handles timeouts gracefully and logs lookup failures at DEBUG level.
"""

import asyncio
import logging
from typing import ClassVar

import aiodns
from aiodns.error import DNSError
from cachetools import TTLCache

from second_hand.config import get_settings

logger = logging.getLogger(__name__)


class DNSService:
    """Service for reverse DNS lookups with caching.

    Uses aiodns for async DNS resolution with configurable timeout.
    Results are cached using TTLCache to avoid repeated lookups.

    Attributes:
        failure_count: Counter for tracking DNS lookup failures (FR-024).
    """

    _instance: ClassVar["DNSService | None"] = None
    failure_count: int = 0

    def __init__(
        self,
        timeout: float | None = None,
        cache_ttl: int | None = None,
        cache_maxsize: int | None = None,
        max_concurrent: int | None = None,
    ) -> None:
        """Initialize the DNS service.

        Args:
            timeout: DNS lookup timeout in seconds. Defaults to config value.
            cache_ttl: Cache TTL in seconds. Defaults to config value.
            cache_maxsize: Maximum cache entries. Defaults to config value.
            max_concurrent: Maximum concurrent lookups. Defaults to config value.
        """
        settings = get_settings()

        self._timeout = timeout if timeout is not None else settings.dns_timeout
        self._cache_ttl = cache_ttl if cache_ttl is not None else settings.dns_cache_ttl
        self._cache_maxsize = (
            cache_maxsize if cache_maxsize is not None else settings.dns_cache_maxsize
        )
        self._max_concurrent = (
            max_concurrent
            if max_concurrent is not None
            else settings.dns_max_concurrent
        )

        self._resolver = aiodns.DNSResolver()
        self._cache: TTLCache[str, str | None] = TTLCache(
            maxsize=self._cache_maxsize, ttl=self._cache_ttl
        )
        self._semaphore = asyncio.Semaphore(self._max_concurrent)

    async def reverse_lookup(self, ip: str) -> str | None:
        """Perform a reverse DNS lookup for an IP address.

        This is the raw lookup without caching. Use cached_reverse_lookup
        for cached lookups.

        Args:
            ip: IP address string (IPv4 or IPv6).

        Returns:
            Hostname string if found, None if lookup fails or times out.
        """
        try:
            result = await asyncio.wait_for(
                self._resolver.gethostbyaddr(ip),
                timeout=self._timeout,
            )
            return result.name
        except TimeoutError:
            logger.debug("DNS reverse lookup timed out for %s", ip)
            self.failure_count += 1
            return None
        except DNSError as e:
            logger.debug("DNS reverse lookup failed for %s: %s", ip, e)
            self.failure_count += 1
            return None
        except Exception as e:
            logger.debug("DNS reverse lookup error for %s: %s", ip, e)
            self.failure_count += 1
            return None

    async def cached_reverse_lookup(self, ip: str) -> str | None:
        """Perform a cached reverse DNS lookup.

        Results are cached to avoid repeated lookups for the same IP.
        Cache entries expire after the configured TTL.

        Args:
            ip: IP address string (IPv4 or IPv6).

        Returns:
            Hostname string if found, None if lookup fails or times out.
        """
        # Check cache first
        if ip in self._cache:
            return self._cache[ip]

        # Perform lookup
        hostname = await self.reverse_lookup(ip)

        # Cache result (including None for failed lookups)
        self._cache[ip] = hostname

        return hostname

    async def batch_reverse_lookup(self, ips: list[str]) -> dict[str, str | None]:
        """Perform batch reverse DNS lookups with concurrency limiting.

        Lookups are performed concurrently but limited by a semaphore
        to avoid overwhelming the DNS resolver.

        Args:
            ips: List of IP address strings.

        Returns:
            Dictionary mapping IP addresses to hostnames (or None).
        """

        async def limited_lookup(ip: str) -> tuple[str, str | None]:
            async with self._semaphore:
                hostname = await self.cached_reverse_lookup(ip)
                return (ip, hostname)

        results = await asyncio.gather(*[limited_lookup(ip) for ip in ips])
        return dict(results)

    def clear_cache(self) -> None:
        """Clear the DNS cache."""
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        """Current number of entries in the cache."""
        return len(self._cache)

    @classmethod
    def get_instance(
        cls,
        timeout: float | None = None,
        cache_ttl: int | None = None,
        cache_maxsize: int | None = None,
        max_concurrent: int | None = None,
    ) -> "DNSService":
        """Get the singleton instance of DNSService.

        Args:
            timeout: DNS lookup timeout (only used on first call).
            cache_ttl: Cache TTL (only used on first call).
            cache_maxsize: Maximum cache entries (only used on first call).
            max_concurrent: Maximum concurrent lookups (only used on first call).

        Returns:
            The singleton DNSService instance.
        """
        if cls._instance is None:
            cls._instance = cls(timeout, cache_ttl, cache_maxsize, max_concurrent)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for testing)."""
        cls._instance = None
