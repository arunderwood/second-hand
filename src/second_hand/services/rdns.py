"""Reverse DNS for NTP source addresses, via dnspython's async resolver.

The resolver runs on the event loop, so a slow nameserver cannot tie up the
thread pool that chronyd calls use.
"""

import asyncio
import ipaddress
import logging
import re
from dataclasses import dataclass

import dns.asyncresolver
import dns.exception
import dns.resolver
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Whole-lookup deadline. dnspython's default of 5s is too slow for a render.
LOOKUP_TIMEOUT_SECONDS = 2.0

ANSWER_CACHE_TTL_SECONDS = 3600
FAILURE_CACHE_TTL_SECONDS = 900

MAX_HOSTNAME_LENGTH = 253
MAX_LABEL_LENGTH = 63

# LDH only. Punycode stays ASCII, so homoglyphs never reach the page.
_LABEL_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


@dataclass
class ReverseDNSResult:
    """Result of a reverse DNS lookup.

    Attributes:
        ip_address: The address that was looked up.
        hostname: The resolved name, or None.
    """

    ip_address: str
    hostname: str | None


def _clean_hostname(value: object) -> str | None:
    """Validate a PTR target, which the address's owner controls.

    Returns:
        The lower-cased name without its trailing dot, or None if it is not a
        valid LDH hostname.
    """
    if value is None:
        return None
    name = str(value).rstrip(".").lower()
    if not name or len(name) > MAX_HOSTNAME_LENGTH:
        return None
    labels = name.split(".")
    if any(len(label) > MAX_LABEL_LENGTH for label in labels):
        return None
    if not all(_LABEL_PATTERN.match(label) for label in labels):
        return None
    return name


class ReverseDNSService:
    """Resolve addresses to hostnames via PTR records, with caching.

    Attributes:
        failure_count: Number of lookups that got no answer at all.
    """

    def __init__(
        self,
        resolver: dns.asyncresolver.Resolver | None,
        *,
        cache_ttl: int = ANSWER_CACHE_TTL_SECONDS,
        failure_ttl: int = FAILURE_CACHE_TTL_SECONDS,
        cache_maxsize: int = 1024,
    ) -> None:
        """Initialize the reverse DNS service.

        Args:
            resolver: Resolver for every query; None disables lookups.
            cache_ttl: How long an answer is cached, in seconds.
            failure_ttl: How long a failed lookup is cached, in seconds.
            cache_maxsize: Maximum entries in each of the two caches.
        """
        self._resolver = resolver
        self._cache: TTLCache[str, ReverseDNSResult] = TTLCache(
            maxsize=cache_maxsize, ttl=cache_ttl
        )
        self._failures: TTLCache[str, ReverseDNSResult] = TTLCache(
            maxsize=cache_maxsize, ttl=failure_ttl
        )
        self.failure_count = 0

    @property
    def enabled(self) -> bool:
        """Whether a resolver is configured."""
        return self._resolver is not None

    async def lookup(self, ip: str) -> ReverseDNSResult:
        """Look up the hostname for an address.

        Args:
            ip: IPv4 or IPv6 address. Refclock names are never queried.

        Returns:
            ReverseDNSResult, with hostname None if there is no usable name.
        """
        cached = self._cache.get(ip) or self._failures.get(ip)
        if cached is not None:
            return cached

        # Unlike GeoIP, private addresses are resolved: LAN peers benefit most.
        if self._resolver is None or not self._is_ip(ip):
            return ReverseDNSResult(ip_address=ip, hostname=None)

        hostname, answered = await self._fetch(ip)
        result = ReverseDNSResult(ip_address=ip, hostname=hostname)
        if answered:
            self._cache[ip] = result
        else:
            self.failure_count += 1
            self._failures[ip] = result
        return result

    async def _fetch(self, ip: str) -> tuple[str | None, bool]:
        """Query one PTR record.

        Returns:
            The hostname or None, and whether the resolver answered. NXDOMAIN
            counts as an answer, so it gets the long cache TTL.
        """
        assert self._resolver is not None
        try:
            answer = await self._resolver.resolve_address(
                ip, lifetime=LOOKUP_TIMEOUT_SECONDS
            )
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            logger.debug("No PTR record for %s", ip)
            return None, True
        except dns.exception.DNSException as e:
            logger.debug("Reverse lookup failed for %s: %s", ip, e)
            return None, False
        # Names are decoration: no failure here may take the dashboard down.
        except Exception as e:
            logger.debug("Reverse lookup error for %s: %s", ip, e)
            return None, False

        target = getattr(answer[0], "target", None)
        hostname = _clean_hostname(target)
        if hostname is None:
            logger.debug("Rejected implausible PTR target for %s: %r", ip, target)
        return hostname, True

    async def batch_lookup(self, ips: list[str]) -> dict[str, ReverseDNSResult]:
        """Look up hostnames concurrently, each distinct address once.

        Args:
            ips: List of address strings.

        Returns:
            Dictionary mapping addresses to ReverseDNSResult objects.
        """
        async with asyncio.TaskGroup() as tg:
            tasks = {ip: tg.create_task(self.lookup(ip)) for ip in dict.fromkeys(ips)}
        return {ip: task.result() for ip, task in tasks.items()}

    @staticmethod
    def _is_ip(value: str) -> bool:
        """Whether the string is an IP address rather than a refclock name."""
        try:
            ipaddress.ip_address(value)
        except ValueError:
            return False
        return True

    @property
    def cache_size(self) -> int:
        """Current number of cached answers and failures."""
        return len(self._cache) + len(self._failures)
