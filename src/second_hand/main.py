"""FastAPI application entry point for second-hand."""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from second_hand import __version__
from second_hand.components import dashboard_page
from second_hand.components.base import error_page
from second_hand.config import get_settings
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
    logger.info("Initializing GeoIP service (ip-api.com)...")
    GeoIPService.get_instance()
    logger.info("GeoIP service initialized")

    yield

    # Shutdown: Cleanup services
    logger.info("Shutting down services...")
    GeoIPService.reset_instance()
    logger.info("Services shut down successfully")


app = FastAPI(
    title="second-hand",
    description="Chrony time statistics dashboard",
    version=__version__,
    lifespan=lifespan,
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
