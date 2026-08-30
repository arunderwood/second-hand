"""Tests for security response headers."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pychrony.testing import make_tracking

from second_hand.config import Settings
from second_hand.middleware import (
    CONTENT_SECURITY_POLICY,
    DOCS_CONTENT_SECURITY_POLICY,
    SecurityHeadersMiddleware,
    build_security_headers,
)
from second_hand.services.chrony import ChronyData


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
    with (
        patch(
            "second_hand.components.dashboard.fetch_chrony_data",
            return_value=mock_data,
        ),
        patch("second_hand.main.fetch_chrony_data", return_value=mock_data),
    ):
        yield mock_data


def _build_client(**kwargs: object) -> TestClient:
    """Build a minimal app wrapped in the middleware under test."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, **kwargs)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


class TestSecurityHeadersOnApplication:
    """Headers must be present on every kind of response."""

    @pytest.mark.parametrize(
        "path",
        ["/", "/health", "/api/sources", "/static/css/style.css", "/does-not-exist"],
    )
    def test_headers_present(
        self,
        client: TestClient,
        mock_fetch_chrony_data: ChronyData,
        path: str,
    ) -> None:
        """HTML, JSON, static, and error responses all carry the headers."""
        response = client.get(path)
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY

    def test_hsts_absent_by_default(
        self, client: TestClient, mock_fetch_chrony_data: ChronyData
    ) -> None:
        """HSTS is omitted unless explicitly configured, since TLS is optional."""
        response = client.get("/")
        assert "strict-transport-security" not in response.headers


class TestContentSecurityPolicy:
    """The policy must be strict but still permit what the dashboard loads."""

    def test_denies_by_default(self) -> None:
        """Anything not explicitly allowed is blocked."""
        assert "default-src 'none'" in CONTENT_SECURITY_POLICY

    def test_no_unsafe_directives(self) -> None:
        """No inline or eval escape hatches are needed."""
        assert "unsafe-inline" not in CONTENT_SECURITY_POLICY
        assert "unsafe-eval" not in CONTENT_SECURITY_POLICY

    @pytest.mark.parametrize(
        "directive",
        [
            "script-src 'self'",
            "img-src 'self'",
            "connect-src 'self'",
            "base-uri 'none'",
            "form-action 'none'",
            "frame-ancestors 'none'",
        ],
    )
    def test_directive_present(self, directive: str) -> None:
        """Each required directive is in the policy."""
        assert directive in CONTENT_SECURITY_POLICY

    def test_allows_google_fonts(self) -> None:
        """style.css imports Google Fonts, so both hosts must be allowed."""
        assert (
            "style-src 'self' https://fonts.googleapis.com" in CONTENT_SECURITY_POLICY
        )
        assert "font-src https://fonts.gstatic.com" in CONTENT_SECURITY_POLICY


class TestHSTSConfiguration:
    """HSTS is opt-in and rendered from settings."""

    def test_enabled_with_subdomains(self) -> None:
        """A non-zero max-age emits the header with includeSubDomains."""
        client = _build_client(hsts_max_age=31536000)
        response = client.get("/ping")
        assert (
            response.headers["strict-transport-security"]
            == "max-age=31536000; includeSubDomains"
        )

    def test_enabled_without_subdomains(self) -> None:
        """includeSubDomains can be turned off."""
        client = _build_client(hsts_max_age=600, hsts_include_subdomains=False)
        response = client.get("/ping")
        assert response.headers["strict-transport-security"] == "max-age=600"

    def test_zero_max_age_disables_header(self) -> None:
        """A max-age of zero omits the header rather than sending max-age=0."""
        client = _build_client(hsts_max_age=0)
        response = client.get("/ping")
        assert "strict-transport-security" not in response.headers


class TestHSTSSettings:
    """Settings validation for the new options."""

    def test_defaults(self) -> None:
        """HSTS defaults to disabled."""
        settings = Settings()
        assert settings.hsts_max_age == 0
        assert settings.hsts_include_subdomains is True

    def test_negative_max_age_rejected(self) -> None:
        """A negative max-age is a configuration error."""
        with pytest.raises(ValueError, match="non-negative"):
            Settings(hsts_max_age=-1)


class TestUnhandledExceptionResponses:
    """500 responses bypass the middleware, so they need their own coverage."""

    def test_server_error_carries_headers(self) -> None:
        """An unhandled exception still returns the security headers."""
        from second_hand.main import app

        client = TestClient(app, raise_server_exceptions=False)

        # /api/sources raises if chronyd access blows up in an unexpected way.
        with patch(
            "second_hand.main.fetch_chrony_data", side_effect=RuntimeError("boom")
        ):
            response = client.get("/api/sources")

        assert response.status_code == 500
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY


class TestHeaderOverwriteSemantics:
    """Security headers must not be weakened by the underlying response."""

    def test_weaker_upstream_value_is_replaced(self) -> None:
        """A handler-set X-Frame-Options is overwritten, not preserved."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/weak")
        async def weak() -> JSONResponse:
            return JSONResponse({}, headers={"x-frame-options": "SAMEORIGIN"})

        response = TestClient(app).get("/weak")
        assert response.headers["x-frame-options"] == "DENY"


class TestBuildSecurityHeaders:
    """The shared builder backs both the middleware and the 500 handler."""

    def test_matches_middleware_headers(self) -> None:
        """Builder output is exactly what the middleware applies."""
        built = build_security_headers(hsts_max_age=600)
        middleware = SecurityHeadersMiddleware(lambda s, r, sd: None, hsts_max_age=600)
        assert built == middleware.headers


class TestDocsPathRelaxation:
    """The relaxed docs policy must apply to docs paths and nowhere else."""

    def _client(self, docs_paths: frozenset[str]) -> TestClient:
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, docs_paths=docs_paths)

        @app.get("/docs")
        async def docs() -> dict[str, str]:
            return {}

        @app.get("/other")
        async def other() -> dict[str, str]:
            return {}

        return TestClient(app)

    def test_listed_path_gets_relaxed_policy(self) -> None:
        """A path in docs_paths receives the docs policy."""
        response = self._client(frozenset({"/docs"})).get("/docs")
        assert (
            response.headers["content-security-policy"] == DOCS_CONTENT_SECURITY_POLICY
        )

    def test_other_paths_stay_strict(self) -> None:
        """Every other path keeps the strict policy."""
        response = self._client(frozenset({"/docs"})).get("/other")
        assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY

    def test_empty_docs_paths_never_relaxes(self) -> None:
        """With no docs_paths configured, even /docs stays strict."""
        response = self._client(frozenset()).get("/docs")
        assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY

    def test_relaxed_policy_keeps_hard_limits(self) -> None:
        """Relaxing for Swagger must not give away framing or base-uri."""
        assert "frame-ancestors 'none'" in DOCS_CONTENT_SECURITY_POLICY
        assert "base-uri 'none'" in DOCS_CONTENT_SECURITY_POLICY
        assert "form-action 'none'" in DOCS_CONTENT_SECURITY_POLICY
        assert "default-src 'none'" in DOCS_CONTENT_SECURITY_POLICY


class TestDocsDisabledInProduction:
    """Dev-only endpoints must not exist when SECOND_HAND_DEBUG is off."""

    @pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
    def test_docs_routes_absent(self, client: TestClient, path: str) -> None:
        """Interactive docs are not served in the default (production) mode."""
        assert client.get(path).status_code == 404


class TestDocsEnabledInDevMode:
    """SECOND_HAND_DEBUG re-enables the docs with a scoped CSP."""

    @pytest.fixture
    def dev_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[TestClient, None, None]:
        """Reimport the app with dev mode on, then restore the default app."""
        import importlib

        import second_hand.main

        monkeypatch.setenv("SECOND_HAND_DEBUG", "true")
        dev_module = importlib.reload(second_hand.main)
        try:
            yield TestClient(dev_module.app)
        finally:
            monkeypatch.delenv("SECOND_HAND_DEBUG")
            importlib.reload(second_hand.main)

    @pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
    def test_docs_routes_present(self, dev_client: TestClient, path: str) -> None:
        """The docs endpoints are served in dev mode."""
        assert dev_client.get(path).status_code == 200

    @pytest.mark.parametrize("path", ["/docs", "/redoc"])
    def test_docs_get_relaxed_policy(self, dev_client: TestClient, path: str) -> None:
        """Swagger UI and ReDoc need the CDN and inline allowances."""
        response = dev_client.get(path)
        assert (
            response.headers["content-security-policy"] == DOCS_CONTENT_SECURITY_POLICY
        )

    def test_dashboard_stays_strict_in_dev_mode(
        self, dev_client: TestClient, mock_fetch_chrony_data: ChronyData
    ) -> None:
        """Enabling docs must not loosen the policy on the dashboard itself."""
        response = dev_client.get("/")
        assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
