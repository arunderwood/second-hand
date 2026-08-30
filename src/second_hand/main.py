"""FastAPI application entry point for second-hand."""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from second_hand import __version__
from second_hand.components import dashboard_page
from second_hand.components.base import error_page
from second_hand.config import get_settings
from second_hand.middleware import SecurityHeadersMiddleware, build_security_headers
from second_hand.services.chrony import enrich_sources, fetch_chrony_data
from second_hand.services.geoip import GeoIPService

logger = logging.getLogger(__name__)

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle for services.

    Initializes GeoIP service at startup and cleans up on shutdown.
    """
    # Startup: Initialize services
    logger.info("Initializing GeoIP service (ipwho.is)...")
    GeoIPService.get_instance()
    logger.info("GeoIP service initialized")

    yield

    # Shutdown: Cleanup services
    logger.info("Shutting down services...")
    GeoIPService.reset_instance()
    logger.info("Services shut down successfully")


_settings = get_settings()

# SECOND_HAND_DEBUG is the dev-mode switch. The interactive API documentation
# is useful locally but is extra unauthenticated attack surface in production,
# where the service binds 0.0.0.0, so those routes only exist in dev mode.
_DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc"})

app = FastAPI(
    title="second-hand",
    description="Chrony time statistics dashboard",
    version=__version__,
    lifespan=lifespan,
    # Deliberately not passing `debug=_settings.debug`: Starlette's
    # ServerErrorMiddleware checks debug before the installed 500 handler, so
    # enabling it would replace `server_error_handler` below with a traceback
    # page that carries no security headers.
    docs_url="/docs" if _settings.debug else None,
    redoc_url="/redoc" if _settings.debug else None,
    openapi_url="/openapi.json" if _settings.debug else None,
)

# Security response headers on responses from routes, static files, and
# handled exceptions. Note that `add_middleware` inserts at the front of the
# stack, so anything added later would wrap this; keep it last if more
# middleware is introduced.
_SECURITY_HEADERS = build_security_headers(
    hsts_max_age=_settings.hsts_max_age,
    hsts_include_subdomains=_settings.hsts_include_subdomains,
)
app.add_middleware(
    SecurityHeadersMiddleware,
    hsts_max_age=_settings.hsts_max_age,
    hsts_include_subdomains=_settings.hsts_include_subdomains,
    docs_paths=_DOCS_PATHS if _settings.debug else frozenset(),
)

# Mount static files if directory exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    """Render the main dashboard page with enriched source data."""
    chrony_data = fetch_chrony_data()

    # Enrich sources with geo data if we have sources
    enriched_sources = None
    if chrony_data.sources:
        enriched_sources = await enrich_sources(chrony_data.sources)

    return str(
        dashboard_page(
            version=__version__,
            chrony_data=chrony_data,
            enriched_sources=enriched_sources,
        )
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


@app.get("/api/sources")
async def api_sources() -> JSONResponse:
    """Get enriched NTP sources as JSON for real-time updates.

    Returns all NTP sources with enriched display data including
    geolocation information.

    Returns:
        JSON response with sources, timestamp, sync status, and refresh interval.
        Returns 503 if unable to connect to chronyd.
    """
    settings = get_settings()
    chrony_data = fetch_chrony_data()

    if chrony_data.error:
        return JSONResponse(
            status_code=503,
            content={
                "error": "connection_failed",
                "message": chrony_data.error,
            },
        )

    # Enrich sources with geo data
    enriched = await enrich_sources(chrony_data.sources)

    # Build response per API contract
    current_time = int(time.time())
    sources_data: list[dict[str, Any]] = []

    for es in enriched:
        source = es.source
        poll_seconds = 2**source.poll
        last_rx_timestamp = int(current_time - source.last_sample_ago)

        # Convert reachability to bits array (newest first for API)
        reach_bits = [(source.reachability >> i) & 1 == 1 for i in range(8)]
        reach_percent = int(sum(reach_bits) / 8 * 100)

        # Map mode to display name
        mode_map = {"CLIENT": "server", "PEER": "peer", "LOCAL": "refclock"}
        mode_display = mode_map.get(source.mode.name, "server")

        sources_data.append(
            {
                "address": source.address,
                "display_name": es.display_name,
                "country_code": es.country_code,
                "country_name": es.country_name,
                "country_flag": es.country_flag,
                "mode": mode_display,
                "mode_raw": source.mode.name,
                "state": source.state.name.replace("_", " ").title(),
                "is_selected": source.state.name == "SELECTED",
                "stratum": source.stratum,
                "poll": poll_seconds,
                "poll_exponent": source.poll,
                "reachability": source.reachability,
                "reachability_bits": reach_bits,
                "reachability_percent": reach_percent,
                "last_rx": source.last_sample_ago,
                "last_rx_timestamp": last_rx_timestamp,
                "latest_meas": source.latest_meas,
                "latest_meas_err": source.latest_meas_err,
            }
        )

    return JSONResponse(
        content={
            "sources": sources_data,
            "timestamp": current_time,
            "is_synchronized": chrony_data.is_synchronized,
            "refresh_interval": settings.refresh_interval,
        }
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> HTMLResponse:
    """Handle 404 errors with a styled error page."""
    return HTMLResponse(
        content=str(error_page(code=404, message="Page not found")),
        status_code=404,
    )


@app.exception_handler(Exception)
async def server_error_handler(request: Request, exc: Exception) -> PlainTextResponse:
    """Handle unhandled exceptions with security headers attached.

    Starlette's ServerErrorMiddleware sits outside the user middleware stack,
    so these responses never pass through SecurityHeadersMiddleware. Setting
    the headers here keeps coverage complete. The exception is re-raised by
    ServerErrorMiddleware afterwards, so it is still logged normally.
    """
    return PlainTextResponse(
        "Internal Server Error",
        status_code=500,
        headers=_SECURITY_HEADERS,
    )


def run() -> None:
    """Run the application with uvicorn."""
    import uvicorn

    from second_hand.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "second_hand.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
