"""Unit tests for the GeoIP service.

These tests never touch the network: every service is built on an
``httpx2.MockTransport``, so a regression that reintroduces a real request
fails rather than silently calling a third party.
"""

import asyncio
import time
from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from second_hand.services.geoip import (
    FAILURE_CACHE_TTL_SECONDS,
    GEOIP_API_URL,
    GeoIPResult,
    GeoIPService,
)

Handler = Callable[[httpx2.Request], httpx2.Response]


class FakeAPI:
    """Mock ipwho.is that records every URL it is asked for."""

    def __init__(self, handler: Handler) -> None:
        self._handler = handler
        self.requested_urls: list[str] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requested_urls.append(str(request.url))
        return self._handler(request)

    def service(self, **kwargs: Any) -> GeoIPService:
        """Build a service whose client can only reach this fake."""
        client = httpx2.AsyncClient(transport=httpx2.MockTransport(self))
        return GeoIPService(client, **kwargs)


def respond(status: int = 200, payload: Any = None) -> FakeAPI:
    """A fake API that always answers with ``payload`` as JSON."""
    body = payload if payload is not None else {}
    return FakeAPI(lambda _request: httpx2.Response(status, json=body))


def fail_with(exc: Exception) -> FakeAPI:
    """A fake API whose transport raises ``exc`` on every request."""

    def handler(_request: httpx2.Request) -> httpx2.Response:
        raise exc

    return FakeAPI(handler)


def success(country_code: Any = "US", country: Any = "United States") -> FakeAPI:
    """A fake API returning a successful ipwho.is style payload."""
    return respond(
        payload={"success": True, "country_code": country_code, "country": country}
    )


def lookup(service: GeoIPService, ip: str) -> GeoIPResult:
    """Run a single lookup to completion."""
    return asyncio.run(service.lookup(ip))


class TestTransport:
    """The lookup must use authenticated transport."""

    def test_api_url_is_https(self) -> None:
        assert GEOIP_API_URL.startswith("https://")

    def test_request_url_is_https_and_contains_ip(self) -> None:
        api = success()
        lookup(api.service(), "8.8.8.8")

        assert len(api.requested_urls) == 1
        url = api.requested_urls[0]
        assert url.startswith("https://")
        assert "8.8.8.8" in url


class TestSuccessfulLookup:
    """Happy path parsing of the ipwho.is response shape."""

    def test_returns_country(self) -> None:
        service = success().service()
        result = lookup(service, "8.8.8.8")

        assert result.ip_address == "8.8.8.8"
        assert result.is_private is False
        assert result.country_code == "US"
        assert result.country_name == "United States"
        assert service.failure_count == 0


class TestPayloadValidation:
    """Third-party fields are validated before reaching the rendered page."""

    def test_country_code_is_upper_cased(self) -> None:
        result = lookup(success(country_code="gb").service(), "8.8.8.8")
        assert result.country_code == "GB"

    @pytest.mark.parametrize(
        "bogus_code",
        [
            "<script>alert(1)</script>",
            "USA",
            "U",
            "",
            "1234",
            "U1",
            None,
            42,
            ["US"],
        ],
    )
    def test_implausible_country_code_is_dropped(self, bogus_code: Any) -> None:
        result = lookup(success(country_code=bogus_code).service(), "8.8.8.8")
        assert result.country_code is None

    @pytest.mark.parametrize(
        "bogus_name",
        ["", "   ", "A" * 65, None, 42],
    )
    def test_implausible_country_name_is_dropped(self, bogus_name: Any) -> None:
        result = lookup(success(country=bogus_name).service(), "8.8.8.8")
        assert result.country_name is None

    def test_missing_fields_degrade_to_none(self) -> None:
        result = lookup(respond(payload={"success": True}).service(), "8.8.8.8")

        assert result.country_code is None
        assert result.country_name is None
        assert result.is_private is False


class TestFailureHandling:
    """Failures degrade gracefully and are counted."""

    @pytest.mark.parametrize(
        "api",
        [
            pytest.param(
                respond(payload={"success": False, "message": "Reserved range"}),
                id="unsuccessful-payload",
            ),
            pytest.param(respond(status=429), id="non-200-status"),
            pytest.param(
                fail_with(httpx2.ReadTimeout("timed out")),
                id="timeout",
            ),
            pytest.param(
                fail_with(httpx2.ConnectError("refused")),
                id="connection-error",
            ),
            pytest.param(fail_with(RuntimeError("boom")), id="unexpected-error"),
            pytest.param(respond(payload=["unexpected"]), id="non-dict-payload"),
            pytest.param(
                FakeAPI(lambda _r: httpx2.Response(200, content=b"<html>")),
                id="invalid-json",
            ),
        ],
    )
    def test_failure_degrades_to_empty_result(self, api: FakeAPI) -> None:
        service = api.service()
        result = lookup(service, "8.8.8.8")

        assert result.country_code is None
        assert result.country_name is None
        assert result.is_private is False
        assert service.failure_count == 1


class TestPrivateAddresses:
    """Private and unparseable addresses never reach the network."""

    @pytest.mark.parametrize(
        "ip",
        ["192.168.1.1", "10.0.0.1", "127.0.0.1", "169.254.1.1", "::1", "fd00::1"],
    )
    def test_private_ip_skips_request(self, ip: str) -> None:
        api = success()
        service = api.service()
        result = lookup(service, ip)

        assert result.is_private is True
        assert result.country_code is None
        assert api.requested_urls == []
        assert service.failure_count == 0

    def test_invalid_ip_skips_request(self) -> None:
        api = success()
        service = api.service()
        result = lookup(service, "not-an-ip")

        assert result.is_private is True
        assert api.requested_urls == []
        assert service.failure_count == 0


class TestCaching:
    """Caching keeps repeat lookups off the network."""

    def test_second_lookup_is_served_from_cache(self) -> None:
        api = success()
        service = api.service()

        first = lookup(service, "8.8.8.8")
        second = lookup(service, "8.8.8.8")

        assert len(api.requested_urls) == 1
        assert first == second
        assert service.cache_size == 1

    def test_failures_are_cached_too(self) -> None:
        api = respond(status=500)
        service = api.service()

        lookup(service, "8.8.8.8")
        lookup(service, "8.8.8.8")

        assert len(api.requested_urls) == 1
        assert service.failure_count == 1

    def test_failures_expire_before_answers(self) -> None:
        """A failed lookup is retried once the short failure TTL passes."""
        api = FakeAPI(
            lambda request: httpx2.Response(
                200,
                json=(
                    {"success": True, "country_code": "US", "country": "US"}
                    if "8.8.8.8" in str(request.url)
                    else {"success": False}
                ),
            )
        )
        service = api.service()
        lookup(service, "8.8.8.8")
        lookup(service, "1.1.1.1")

        later = time.monotonic() + FAILURE_CACHE_TTL_SECONDS + 1
        service._cache.expire(later)
        service._failures.expire(later)

        lookup(service, "8.8.8.8")
        lookup(service, "1.1.1.1")
        assert api.requested_urls.count(GEOIP_API_URL.format(ip="8.8.8.8")) == 1
        assert api.requested_urls.count(GEOIP_API_URL.format(ip="1.1.1.1")) == 2

    def test_cache_respects_maxsize(self) -> None:
        service = success().service(cache_maxsize=2)

        for ip in ("8.8.8.8", "1.1.1.1", "9.9.9.9"):
            lookup(service, ip)

        assert service.cache_size == 2


class TestBatchLookup:
    """Batch lookups mix private and public addresses correctly."""

    def test_batch_lookup(self) -> None:
        api = success()
        service = api.service()
        results = asyncio.run(
            service.batch_lookup(["8.8.8.8", "192.168.1.1", "8.8.8.8"])
        )

        assert set(results) == {"8.8.8.8", "192.168.1.1"}
        assert results["8.8.8.8"].country_code == "US"
        assert results["192.168.1.1"].is_private is True
        # Only the public address is fetched, and only once despite repeating.
        assert len(api.requested_urls) == 1

    def test_lookups_run_concurrently(self) -> None:
        """A batch takes about as long as one lookup, not one per address."""
        in_flight = 0
        peak = 0

        async def handler(_request: httpx2.Request) -> httpx2.Response:
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1
            return httpx2.Response(200, json={"success": True})

        client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        service = GeoIPService(client)
        asyncio.run(service.batch_lookup(["8.8.8.8", "1.1.1.1", "9.9.9.9"]))

        assert peak == 3

    def test_empty_batch(self) -> None:
        assert asyncio.run(success().service().batch_lookup([])) == {}
