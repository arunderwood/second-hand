"""Tests for FastAPI application endpoints."""

from collections.abc import Generator
from unittest.mock import patch

import dns.asyncresolver
import dns.resolver
import httpx2
import pytest
from fastapi.testclient import TestClient
from pychrony.testing import make_source, make_tracking

from second_hand.main import _build_resolver, app, get_geoip, get_rdns
from second_hand.services.chrony import ChronyData
from second_hand.services.geoip import GeoIPService
from second_hand.services.rdns import (
    LOOKUP_TIMEOUT_SECONDS,
    ReverseDNSResult,
    ReverseDNSService,
)


@pytest.fixture
def mock_fetch_chrony_data() -> Generator[ChronyData, None, None]:
    """Mock fetch_chrony_data to avoid connecting to chronyd."""
    mock_data = ChronyData(
        tracking=make_tracking(),
        sources=[],
        source_stats=[],
        rtc=None,
        error=None,
    )
    with patch("second_hand.main.fetch_chrony_data", return_value=mock_data):
        yield mock_data


@pytest.fixture
def mock_chrony_sources() -> Generator[ChronyData, None, None]:
    """Mock chronyd reporting one public and one private source."""
    mock_data = ChronyData(
        tracking=make_tracking(),
        sources=[make_source(address="8.8.8.8"), make_source(address="192.168.1.1")],
        source_stats=[],
        rtc=None,
        error=None,
    )
    with patch("second_hand.main.fetch_chrony_data", return_value=mock_data):
        yield mock_data


@pytest.fixture
def geoip_requests() -> Generator[list[str], None, None]:
    """Serve GeoIP from a fake ipwho.is and record every URL it is asked for."""
    requested: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requested.append(str(request.url))
        return httpx2.Response(
            200, json={"success": True, "country_code": "DE", "country": "Germany"}
        )

    service = GeoIPService(httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))
    app.dependency_overrides[get_geoip] = lambda: service
    try:
        yield requested
    finally:
        app.dependency_overrides.pop(get_geoip, None)


@pytest.fixture
def resolved_hostnames() -> Generator[dict[str, str], None, None]:
    """Resolve 8.8.8.8 from a fake resolver, leaving the private source bare."""
    names = {"8.8.8.8": "dns.google"}

    class FakeRdns(ReverseDNSService):
        async def lookup(self, ip: str) -> ReverseDNSResult:
            return ReverseDNSResult(ip_address=ip, hostname=names.get(ip))

    app.dependency_overrides[get_rdns] = lambda: FakeRdns(None)
    try:
        yield names
    finally:
        app.dependency_overrides.pop(get_rdns, None)


class TestDashboardEndpoint:
    """Tests for the dashboard endpoint."""

    def test_get_dashboard_returns_200(
        self, client: TestClient, mock_fetch_chrony_data: ChronyData
    ) -> None:
        """GET / should return 200 status code."""
        response = client.get("/")
        assert response.status_code == 200

    def test_get_dashboard_returns_html(
        self, client: TestClient, mock_fetch_chrony_data: ChronyData
    ) -> None:
        """GET / should return HTML content type."""
        response = client.get("/")
        assert "text/html" in response.headers["content-type"]

    def test_get_dashboard_contains_title(
        self, client: TestClient, mock_fetch_chrony_data: ChronyData
    ) -> None:
        """GET / should return page with second-hand title."""
        response = client.get("/")
        assert "second-hand" in response.text

    def test_dashboard_shows_source_country(
        self,
        client: TestClient,
        mock_chrony_sources: ChronyData,
        geoip_requests: list[str],
    ) -> None:
        """Public sources are rendered with the country GeoIP found for them."""
        response = client.get("/")

        assert response.status_code == 200
        assert 'title="Germany"' in response.text
        assert len(geoip_requests) == 1

    def test_dashboard_shows_resolved_hostname(
        self,
        client: TestClient,
        mock_chrony_sources: ChronyData,
        geoip_requests: list[str],
        resolved_hostnames: dict[str, str],
    ) -> None:
        """A resolved source shows its name, with the address in the title."""
        response = client.get("/")

        assert '<span class="source-name" title="8.8.8.8">dns.google</span>' in (
            response.text
        )

    def test_dashboard_shows_address_when_unresolved(
        self,
        client: TestClient,
        mock_chrony_sources: ChronyData,
        geoip_requests: list[str],
        resolved_hostnames: dict[str, str],
    ) -> None:
        """No PTR record means no title, so no hover affordance either."""
        response = client.get("/")

        assert '<span class="source-name">192.168.1.1</span>' in response.text

    def test_dashboard_rows_key_on_the_address_not_the_name(
        self,
        client: TestClient,
        mock_chrony_sources: ChronyData,
        geoip_requests: list[str],
        resolved_hostnames: dict[str, str],
    ) -> None:
        """dashboard.js reloads the page if data-address stops matching."""
        response = client.get("/")

        assert 'data-address="8.8.8.8"' in response.text
        assert 'data-address="dns.google"' not in response.text


class TestSourcesEndpoint:
    """Tests for the JSON sources endpoint."""

    def test_sources_are_enriched_with_country(
        self,
        client: TestClient,
        mock_chrony_sources: ChronyData,
        geoip_requests: list[str],
    ) -> None:
        """Public sources get a country; private ones are never looked up."""
        response = client.get("/api/sources")

        assert response.status_code == 200
        by_address = {s["address"]: s for s in response.json()["sources"]}
        assert by_address["8.8.8.8"]["country_code"] == "DE"
        assert by_address["8.8.8.8"]["country_name"] == "Germany"
        assert by_address["192.168.1.1"]["country_code"] is None
        assert len(geoip_requests) == 1
        assert "8.8.8.8" in geoip_requests[0]

    def test_sources_are_enriched_with_hostname(
        self,
        client: TestClient,
        mock_chrony_sources: ChronyData,
        geoip_requests: list[str],
        resolved_hostnames: dict[str, str],
    ) -> None:
        """display_name carries the name, falling back to the address."""
        response = client.get("/api/sources")

        assert response.status_code == 200
        by_address = {s["address"]: s for s in response.json()["sources"]}
        assert by_address["8.8.8.8"]["hostname"] == "dns.google"
        assert by_address["8.8.8.8"]["display_name"] == "dns.google"
        assert by_address["192.168.1.1"]["hostname"] is None
        assert by_address["192.168.1.1"]["display_name"] == "192.168.1.1"


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check_returns_200(self, client: TestClient) -> None:
        """GET /health should return 200 status code."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_returns_healthy_status(self, client: TestClient) -> None:
        """GET /health should return healthy status."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_check_includes_version(self, client: TestClient) -> None:
        """GET /health should include version in response."""
        from second_hand import __version__

        response = client.get("/health")
        data = response.json()
        assert "version" in data
        assert data["version"] == __version__


class TestNotFoundHandler:
    """Tests for 404 error handling."""

    def test_not_found_returns_404(self, client: TestClient) -> None:
        """Non-existent path should return 404 status code."""
        response = client.get("/nonexistent-path")
        assert response.status_code == 404

    def test_not_found_returns_html(self, client: TestClient) -> None:
        """404 response should be HTML, not JSON."""
        response = client.get("/nonexistent-path")
        assert "text/html" in response.headers["content-type"]

    def test_not_found_contains_error_message(self, client: TestClient) -> None:
        """404 page should contain an error message."""
        response = client.get("/nonexistent-path")
        assert "404" in response.text or "not found" in response.text.lower()


class TestResolverConfiguration:
    """The resolver is built at startup and must never block it."""

    def test_resolver_carries_the_lookup_deadline(self) -> None:
        resolver = _build_resolver()

        assert resolver is not None
        assert resolver.lifetime == LOOKUP_TIMEOUT_SECONDS

    def test_unusable_resolv_conf_disables_hostnames(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A host with no resolver configuration still serves the dashboard."""

        def raise_unconfigured(*args: object, **kwargs: object) -> None:
            raise dns.resolver.NoResolverConfiguration("no nameservers")

        monkeypatch.setattr(dns.asyncresolver, "Resolver", raise_unconfigured)

        assert _build_resolver() is None

    def test_dashboard_serves_without_a_resolver(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mock_chrony_sources: ChronyData,
        geoip_requests: list[str],
    ) -> None:
        """The whole app comes up, addresses and all, with DNS unavailable."""

        def raise_unconfigured(*args: object, **kwargs: object) -> None:
            raise dns.resolver.NoResolverConfiguration("no nameservers")

        monkeypatch.setattr(dns.asyncresolver, "Resolver", raise_unconfigured)
        app.dependency_overrides.pop(get_rdns, None)

        with TestClient(app) as unguarded:
            response = unguarded.get("/")

        assert response.status_code == 200
        assert '<span class="source-name">8.8.8.8</span>' in response.text
