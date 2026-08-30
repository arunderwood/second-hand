"""Unit tests for the GeoIP service.

These tests never touch the network: ``aiohttp.ClientSession`` is always
patched out, so a regression that reintroduces a real request will fail
rather than silently call a third party.
"""

import asyncio
from types import TracebackType
from typing import Any
from unittest.mock import patch

import pytest

from second_hand.services.geoip import (
    GEOIP_API_URL,
    GeoIPResult,
    GeoIPService,
)


class FakeResponse:
    """Stand-in for an ``aiohttp`` response used as an async context manager."""

    def __init__(
        self,
        status: int = 200,
        payload: Any = None,
        raise_on_enter: BaseException | None = None,
    ) -> None:
        self.status = status
        self._payload = payload if payload is not None else {}
        self._raise_on_enter = raise_on_enter

    async def json(self) -> Any:
        return self._payload

    async def __aenter__(self) -> "FakeResponse":
        if self._raise_on_enter is not None:
            raise self._raise_on_enter
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False


class FakeSession:
    """Stand-in for ``aiohttp.ClientSession`` that records requested URLs."""

    def __init__(self, response: FakeResponse) -> None:
        self._response = response
        self.requested_urls: list[str] = []

    def get(self, url: str, **_kwargs: Any) -> FakeResponse:
        self.requested_urls.append(url)
        return self._response

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False


def lookup(service: GeoIPService, ip: str, session: FakeSession) -> GeoIPResult:
    """Run a lookup with ``aiohttp.ClientSession`` patched to ``session``."""
    with patch(
        "second_hand.services.geoip.aiohttp.ClientSession", return_value=session
    ):
        return asyncio.run(service.lookup(ip))


def success_session(
    country_code: Any = "US", country: Any = "United States"
) -> FakeSession:
    """Build a session returning a successful ipwho.is style payload."""
    return FakeSession(
        FakeResponse(
            status=200,
            payload={
                "success": True,
                "country_code": country_code,
                "country": country,
            },
        )
    )


@pytest.fixture
def service() -> GeoIPService:
    """Provide a fresh (non-singleton) GeoIP service."""
    return GeoIPService()


class TestTransport:
    """The lookup must use authenticated transport."""

    def test_api_url_is_https(self) -> None:
        assert GEOIP_API_URL.startswith("https://")

    def test_request_url_is_https_and_contains_ip(self, service: GeoIPService) -> None:
        session = success_session()
        lookup(service, "8.8.8.8", session)

        assert len(session.requested_urls) == 1
        url = session.requested_urls[0]
        assert url.startswith("https://")
        assert "8.8.8.8" in url


class TestSuccessfulLookup:
    """Happy path parsing of the ipwho.is response shape."""

    def test_returns_country(self, service: GeoIPService) -> None:
        result = lookup(service, "8.8.8.8", success_session())

        assert result.ip_address == "8.8.8.8"
        assert result.is_private is False
        assert result.country_code == "US"
        assert result.country_name == "United States"
        assert service.failure_count == 0


class TestPayloadValidation:
    """Third-party fields are validated before reaching the rendered page."""

    def test_country_code_is_upper_cased(self, service: GeoIPService) -> None:
        result = lookup(service, "8.8.8.8", success_session(country_code="gb"))
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
    def test_implausible_country_code_is_dropped(
        self, service: GeoIPService, bogus_code: Any
    ) -> None:
        result = lookup(service, "8.8.8.8", success_session(country_code=bogus_code))
        assert result.country_code is None

    @pytest.mark.parametrize(
        "bogus_name",
        ["", "   ", "A" * 65, None, 42],
    )
    def test_implausible_country_name_is_dropped(
        self, service: GeoIPService, bogus_name: Any
    ) -> None:
        result = lookup(service, "8.8.8.8", success_session(country=bogus_name))
        assert result.country_name is None

    def test_missing_fields_degrade_to_none(self, service: GeoIPService) -> None:
        session = FakeSession(FakeResponse(status=200, payload={"success": True}))
        result = lookup(service, "8.8.8.8", session)

        assert result.country_code is None
        assert result.country_name is None
        assert result.is_private is False


class TestFailureHandling:
    """Failures degrade gracefully and are counted."""

    def test_unsuccessful_payload(self, service: GeoIPService) -> None:
        session = FakeSession(
            FakeResponse(
                status=200,
                payload={"success": False, "message": "Reserved range"},
            )
        )
        result = lookup(service, "8.8.8.8", session)

        assert result.country_code is None
        assert result.country_name is None
        assert result.is_private is False
        assert service.failure_count == 1

    def test_non_200_status(self, service: GeoIPService) -> None:
        session = FakeSession(FakeResponse(status=429, payload={}))
        result = lookup(service, "8.8.8.8", session)

        assert result.country_code is None
        assert service.failure_count == 1

    def test_timeout(self, service: GeoIPService) -> None:
        session = FakeSession(FakeResponse(raise_on_enter=TimeoutError()))
        result = lookup(service, "8.8.8.8", session)

        assert result.country_code is None
        assert service.failure_count == 1

    def test_unexpected_error(self, service: GeoIPService) -> None:
        session = FakeSession(FakeResponse(raise_on_enter=RuntimeError("boom")))
        result = lookup(service, "8.8.8.8", session)

        assert result.country_code is None
        assert service.failure_count == 1

    def test_non_dict_payload(self, service: GeoIPService) -> None:
        session = FakeSession(FakeResponse(status=200, payload=["unexpected"]))
        result = lookup(service, "8.8.8.8", session)

        assert result.country_code is None
        assert service.failure_count == 1


class TestPrivateAddresses:
    """Private and unparseable addresses never reach the network."""

    @pytest.mark.parametrize(
        "ip",
        ["192.168.1.1", "10.0.0.1", "127.0.0.1", "169.254.1.1", "::1", "fd00::1"],
    )
    def test_private_ip_skips_request(self, service: GeoIPService, ip: str) -> None:
        session = success_session()
        result = lookup(service, ip, session)

        assert result.is_private is True
        assert result.country_code is None
        assert session.requested_urls == []
        assert service.failure_count == 0

    def test_invalid_ip_skips_request(self, service: GeoIPService) -> None:
        session = success_session()
        result = lookup(service, "not-an-ip", session)

        assert result.is_private is True
        assert session.requested_urls == []
        assert service.failure_count == 0


class TestCaching:
    """The TTLCache keeps repeat lookups off the network."""

    def test_second_lookup_is_served_from_cache(self, service: GeoIPService) -> None:
        session = success_session()

        first = lookup(service, "8.8.8.8", session)
        second = lookup(service, "8.8.8.8", session)

        assert len(session.requested_urls) == 1
        assert first == second
        assert service.cache_size == 1

    def test_failures_are_cached_too(self, service: GeoIPService) -> None:
        session = FakeSession(FakeResponse(status=500, payload={}))

        lookup(service, "8.8.8.8", session)
        lookup(service, "8.8.8.8", session)

        assert len(session.requested_urls) == 1
        assert service.failure_count == 1

    def test_cache_respects_maxsize(self) -> None:
        service = GeoIPService(cache_maxsize=2)
        session = success_session()

        for ip in ("8.8.8.8", "1.1.1.1", "9.9.9.9"):
            lookup(service, ip, session)

        assert service.cache_size == 2


class TestBatchLookup:
    """Batch lookups mix private and public addresses correctly."""

    def test_batch_lookup(self, service: GeoIPService) -> None:
        session = success_session()
        with patch(
            "second_hand.services.geoip.aiohttp.ClientSession", return_value=session
        ):
            results = asyncio.run(
                service.batch_lookup(["8.8.8.8", "192.168.1.1", "8.8.8.8"])
            )

        assert set(results) == {"8.8.8.8", "192.168.1.1"}
        assert results["8.8.8.8"].country_code == "US"
        assert results["192.168.1.1"].is_private is True
        # Only the public address is fetched, and only once thanks to the cache.
        assert len(session.requested_urls) == 1

    def test_empty_batch(self, service: GeoIPService) -> None:
        assert asyncio.run(service.batch_lookup([])) == {}


class TestSingleton:
    """Singleton lifecycle used by the FastAPI lifespan."""

    def test_get_instance_is_stable(self) -> None:
        GeoIPService.reset_instance()
        try:
            assert GeoIPService.get_instance() is GeoIPService.get_instance()
        finally:
            GeoIPService.reset_instance()

    def test_reset_instance_creates_a_new_object(self) -> None:
        GeoIPService.reset_instance()
        try:
            first = GeoIPService.get_instance()
            GeoIPService.reset_instance()
            assert GeoIPService.get_instance() is not first
        finally:
            GeoIPService.reset_instance()

    def test_is_available(self, service: GeoIPService) -> None:
        assert service.is_available is True
