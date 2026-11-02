"""Unit tests for the reverse DNS service, all against a FakeResolver."""

import asyncio
import time
from collections.abc import Callable
from typing import Any, cast

import dns.exception
import dns.name
import dns.resolver
import pytest

from second_hand.services.rdns import (
    FAILURE_CACHE_TTL_SECONDS,
    LOOKUP_TIMEOUT_SECONDS,
    MAX_HOSTNAME_LENGTH,
    MAX_LABEL_LENGTH,
    ReverseDNSResult,
    ReverseDNSService,
    _clean_hostname,
)

Handler = Callable[[str], Any]


class FakePTR:
    """One PTR rdata, carrying only the attribute the service reads."""

    def __init__(self, target: object) -> None:
        self.target = target


class FakeResolver:
    """Resolver stub that records every address it is asked to resolve."""

    def __init__(self, handler: Handler) -> None:
        self._handler = handler
        self.queried: list[str] = []
        self.lifetimes: list[float | None] = []

    async def resolve_address(self, ipaddr: str, **kwargs: Any) -> Any:
        self.queried.append(ipaddr)
        self.lifetimes.append(kwargs.get("lifetime"))
        return self._handler(ipaddr)

    def service(self, **kwargs: Any) -> ReverseDNSService:
        """Build a service that can only reach this fake."""
        return ReverseDNSService(cast(Any, self), **kwargs)


def answers(name: object) -> FakeResolver:
    """A fake resolver answering every query with ``name`` as the PTR target."""
    return FakeResolver(lambda _ip: [FakePTR(name)])


def resolves(name: str) -> FakeResolver:
    """A fake resolver answering with ``name`` parsed as a real DNS name."""
    return answers(dns.name.from_text(name))


def raises(exc: Exception) -> FakeResolver:
    """A fake resolver whose every query raises ``exc``."""

    def handler(_ip: str) -> Any:
        raise exc

    return FakeResolver(handler)


def lookup(service: ReverseDNSService, ip: str) -> ReverseDNSResult:
    """Run a single lookup to completion."""
    return asyncio.run(service.lookup(ip))


def timeout() -> dns.resolver.LifetimeTimeout:
    """A dnspython deadline error, which needs both of its keyword args."""
    return dns.resolver.LifetimeTimeout(timeout=1.0, errors=[])


class TestSuccessfulLookup:
    """A PTR record becomes a displayable hostname."""

    def test_resolves_to_hostname(self) -> None:
        resolver = resolves("t1.time.bf1.yahoo.com")
        result = lookup(resolver.service(), "72.30.35.89")

        assert result == ReverseDNSResult(
            ip_address="72.30.35.89", hostname="t1.time.bf1.yahoo.com"
        )
        assert resolver.queried == ["72.30.35.89"]

    def test_trailing_dot_is_stripped(self) -> None:
        """dns.name.Name stringifies as a fully qualified name."""
        assert str(dns.name.from_text("dns.google")) == "dns.google."

        assert lookup(resolves("dns.google").service(), "8.8.8.8").hostname == (
            "dns.google"
        )

    def test_name_is_lowercased(self) -> None:
        """DNS is case-insensitive, so two cases must not render differently."""
        result = lookup(resolves("T1.Time.BF1.Yahoo.COM").service(), "72.30.35.89")

        assert result.hostname == "t1.time.bf1.yahoo.com"

    def test_single_label_name_is_kept(self) -> None:
        """A LAN peer may legitimately have no domain part."""
        assert lookup(resolves("router").service(), "192.168.1.1").hostname == "router"

    def test_lookup_carries_the_deadline(self) -> None:
        resolver = resolves("dns.google")
        lookup(resolver.service(), "8.8.8.8")

        assert resolver.lifetimes == [LOOKUP_TIMEOUT_SECONDS]

    def test_ipv6_is_resolved(self) -> None:
        resolver = resolves("dns.google")
        result = lookup(resolver.service(), "2001:4860:4860::8888")

        assert result.hostname == "dns.google"
        assert resolver.queried == ["2001:4860:4860::8888"]


class TestHostnameValidation:
    """A PTR target is set by whoever holds the address, so it is validated."""

    @pytest.mark.parametrize(
        "target",
        [
            pytest.param("", id="empty"),
            pytest.param(".", id="root"),
            pytest.param(None, id="none"),
            pytest.param("host name.example.com", id="space"),
            pytest.param("host\nname.example.com", id="newline"),
            pytest.param("host\x00.example.com", id="null byte"),
            pytest.param("<script>.example.com", id="markup"),
            pytest.param("héllo.example.com", id="non-ascii"),
            pytest.param("-leading.example.com", id="leading hyphen"),
            pytest.param("trailing-.example.com", id="trailing hyphen"),
            pytest.param("host..example.com", id="empty label"),
            pytest.param("under_score.example.com", id="underscore"),
            pytest.param(
                "a" * (MAX_LABEL_LENGTH + 1) + ".example.com", id="long label"
            ),
            pytest.param("a." * MAX_HOSTNAME_LENGTH + "example.com", id="long name"),
        ],
    )
    def test_implausible_targets_are_rejected(self, target: object) -> None:
        assert _clean_hostname(target) is None

    @pytest.mark.parametrize(
        ("target", "expected"),
        [
            pytest.param(
                "xn--bcher-kva.example.com", "xn--bcher-kva.example.com", id="punycode"
            ),
            pytest.param("ns1.example.com.", "ns1.example.com", id="fqdn"),
            pytest.param(
                "a" * MAX_LABEL_LENGTH, "a" * MAX_LABEL_LENGTH, id="max label"
            ),
            pytest.param(
                "host-1.sub-2.example.com", "host-1.sub-2.example.com", id="hyphens"
            ),
        ],
    )
    def test_plausible_targets_are_kept(self, target: str, expected: str) -> None:
        assert _clean_hostname(target) == expected

    def test_punycode_is_not_decoded(self) -> None:
        """An A-label stays ASCII: homoglyphs must not reach the page."""
        result = lookup(answers("xn--80ak6aa92e.example.com").service(), "203.0.113.1")

        assert result.hostname == "xn--80ak6aa92e.example.com"

    def test_rejected_target_degrades_to_no_hostname(self) -> None:
        result = lookup(answers("not a hostname").service(), "203.0.113.1")

        assert result.hostname is None

    def test_rejected_target_is_not_a_failure(self) -> None:
        """The resolver answered; the answer was simply unusable."""
        service = answers("not a hostname").service()
        lookup(service, "203.0.113.1")

        assert service.failure_count == 0

    def test_answer_without_a_target_is_handled(self) -> None:
        result = lookup(FakeResolver(lambda _ip: [object()]).service(), "203.0.113.1")

        assert result.hostname is None


class TestNoPtrRecord:
    """An address with no PTR record has a definitive answer, not a failure."""

    @pytest.mark.parametrize(
        "exc",
        [
            pytest.param(dns.resolver.NXDOMAIN(), id="nxdomain"),
            pytest.param(dns.resolver.NoAnswer(), id="no answer"),
        ],
    )
    def test_missing_record_yields_no_hostname(self, exc: Exception) -> None:
        result = lookup(raises(exc).service(), "38.28.93.135")

        assert result == ReverseDNSResult(ip_address="38.28.93.135", hostname=None)

    def test_missing_record_is_not_counted_as_a_failure(self) -> None:
        service = raises(dns.resolver.NXDOMAIN()).service()
        lookup(service, "38.28.93.135")

        assert service.failure_count == 0

    def test_missing_record_is_cached_as_an_answer(self) -> None:
        """NXDOMAIN is authoritative, so it earns the long TTL, not a retry."""
        resolver = raises(dns.resolver.NXDOMAIN())
        service = resolver.service()
        lookup(service, "38.28.93.135")
        lookup(service, "38.28.93.135")

        assert resolver.queried == ["38.28.93.135"]
        later = time.monotonic() + FAILURE_CACHE_TTL_SECONDS + 1
        service._failures.expire(later)
        lookup(service, "38.28.93.135")
        assert resolver.queried == ["38.28.93.135"]


class TestFailureHandling:
    """A resolver that gives no answer degrades the cell, not the page."""

    @pytest.mark.parametrize(
        "exc",
        [
            pytest.param(timeout(), id="lifetime timeout"),
            pytest.param(dns.resolver.NoNameservers(), id="no nameservers"),
            pytest.param(dns.exception.DNSException(), id="generic dns error"),
            pytest.param(RuntimeError("boom"), id="unexpected error"),
        ],
    )
    def test_failure_yields_no_hostname(self, exc: Exception) -> None:
        service = raises(exc).service()
        result = lookup(service, "72.30.35.89")

        assert result == ReverseDNSResult(ip_address="72.30.35.89", hostname=None)
        assert service.failure_count == 1


class TestAddressesThatAreNotQueried:
    """Only real addresses reach the resolver."""

    @pytest.mark.parametrize("address", ["PPS", "NMEA", "GPS", "", "not-an-ip"])
    def test_refclock_names_are_never_resolved(self, address: str) -> None:
        resolver = resolves("dns.google")
        result = lookup(resolver.service(), address)

        assert result == ReverseDNSResult(ip_address=address, hostname=None)
        assert resolver.queried == []

    @pytest.mark.parametrize("address", ["192.168.1.1", "10.0.0.1", "fd00::1"])
    def test_private_addresses_are_resolved(self, address: str) -> None:
        """Unlike GeoIP: a LAN peer is where a name helps most."""
        resolver = resolves("peer.lan")
        result = lookup(resolver.service(), address)

        assert result.hostname == "peer.lan"
        assert resolver.queried == [address]


class TestDisabledService:
    """A host with no resolver configuration still serves the dashboard."""

    def test_lookup_returns_no_hostname(self) -> None:
        service = ReverseDNSService(None)

        assert lookup(service, "72.30.35.89") == ReverseDNSResult(
            ip_address="72.30.35.89", hostname=None
        )
        assert service.enabled is False
        assert service.failure_count == 0

    def test_batch_lookup_covers_every_address(self) -> None:
        service = ReverseDNSService(None)
        results = asyncio.run(service.batch_lookup(["72.30.35.89", "PPS"]))

        assert {ip: r.hostname for ip, r in results.items()} == {
            "72.30.35.89": None,
            "PPS": None,
        }

    def test_nothing_is_cached(self) -> None:
        """A disabled service must not pin answers it never looked up."""
        service = ReverseDNSService(None)
        lookup(service, "72.30.35.89")

        assert service.cache_size == 0


class TestCaching:
    """Caching keeps repeat lookups off the resolver."""

    def test_second_lookup_is_served_from_cache(self) -> None:
        resolver = resolves("dns.google")
        service = resolver.service()

        first = lookup(service, "8.8.8.8")
        second = lookup(service, "8.8.8.8")

        assert resolver.queried == ["8.8.8.8"]
        assert first == second
        assert service.cache_size == 1

    def test_failures_are_cached_too(self) -> None:
        resolver = raises(timeout())
        service = resolver.service()

        lookup(service, "8.8.8.8")
        lookup(service, "8.8.8.8")

        assert resolver.queried == ["8.8.8.8"]
        assert service.failure_count == 1

    def test_failures_expire_before_answers(self) -> None:
        """A failed lookup is retried once the short failure TTL passes."""

        def handler(ip: str) -> Any:
            if ip == "8.8.8.8":
                return [FakePTR(dns.name.from_text("dns.google"))]
            raise timeout()

        resolver = FakeResolver(handler)
        service = resolver.service()
        lookup(service, "8.8.8.8")
        lookup(service, "1.1.1.1")

        later = time.monotonic() + FAILURE_CACHE_TTL_SECONDS + 1
        service._cache.expire(later)
        service._failures.expire(later)

        lookup(service, "8.8.8.8")
        lookup(service, "1.1.1.1")
        assert resolver.queried.count("8.8.8.8") == 1
        assert resolver.queried.count("1.1.1.1") == 2

    def test_cache_respects_maxsize(self) -> None:
        service = resolves("dns.google").service(cache_maxsize=2)

        for ip in ("8.8.8.8", "1.1.1.1", "9.9.9.9"):
            lookup(service, ip)

        assert service.cache_size == 2


class TestBatchLookup:
    """Many sources resolve in one pass."""

    def test_every_address_is_present(self) -> None:
        service = resolves("peer.lan").service()
        results = asyncio.run(service.batch_lookup(["192.168.1.1", "10.0.0.1", "PPS"]))

        assert {ip: r.hostname for ip, r in results.items()} == {
            "192.168.1.1": "peer.lan",
            "10.0.0.1": "peer.lan",
            "PPS": None,
        }

    def test_duplicates_are_queried_once(self) -> None:
        resolver = resolves("dns.google")
        service = resolver.service()

        results = asyncio.run(service.batch_lookup(["8.8.8.8", "8.8.8.8", "8.8.8.8"]))

        assert resolver.queried == ["8.8.8.8"]
        assert results["8.8.8.8"].hostname == "dns.google"

    def test_lookups_run_concurrently(self) -> None:
        in_flight = 0
        peak = 0

        class ConcurrentResolver(FakeResolver):
            """Counts how many queries overlap inside the resolver."""

            async def resolve_address(self, ipaddr: str, **kwargs: Any) -> Any:
                nonlocal in_flight, peak
                self.queried.append(ipaddr)
                in_flight += 1
                peak = max(peak, in_flight)
                await asyncio.sleep(0.01)
                in_flight -= 1
                return [FakePTR(dns.name.from_text("dns.google"))]

        service = ConcurrentResolver(lambda _ip: None).service()
        asyncio.run(service.batch_lookup(["8.8.8.8", "1.1.1.1", "9.9.9.9"]))

        assert peak == 3
