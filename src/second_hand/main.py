"""FastAPI application entry point for second-hand."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, TypedDict

import dns.asyncresolver
import dns.resolver
import httpx2
import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from second_hand import __version__
from second_hand.components import dashboard_page
from second_hand.components.base import error_page
from second_hand.config import get_settings
from second_hand.fonts import router as fonts_router
from second_hand.middleware import SecurityHeadersMiddleware, build_security_headers
from second_hand.schemas import ApiError, SourcesResponse
from second_hand.services.chrony import enrich_sources, fetch_chrony_data
from second_hand.services.geoip import GeoIPService
from second_hand.services.rdns import LOOKUP_TIMEOUT_SECONDS, ReverseDNSService

logger = logging.getLogger(__name__)

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"


class AppState(TypedDict):
    """Per-application services, exposed to requests as ``request.state``."""

    geoip: GeoIPService
    rdns: ReverseDNSService


def _build_resolver() -> dns.asyncresolver.Resolver | None:
    """Configure a resolver from resolv.conf, or None so startup never fails."""
    try:
        resolver = dns.asyncresolver.Resolver()
    except dns.resolver.NoResolverConfiguration as e:
        logger.warning("Source hostnames unavailable, no usable resolv.conf: %s", e)
        return None
    resolver.lifetime = LOOKUP_TIMEOUT_SECONDS
    return resolver


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[AppState]:
    """Own the services that live as long as the application.

    The HTTP client is shared by every GeoIP lookup so connections to ipwho.is
    are pooled, and it is closed on shutdown.
    """
    resolver = _build_resolver()
    async with httpx2.AsyncClient() as client:
        logger.info("GeoIP service (ipwho.is) ready")
        if resolver is not None:
            nameservers = ", ".join(str(ns) for ns in resolver.nameservers)
            logger.info("Reverse DNS service ready (%s)", nameservers)
        yield {
            "geoip": GeoIPService(client),
            "rdns": ReverseDNSService(resolver),
        }


async def get_geoip(request: Request) -> GeoIPService:
    """Dependency: the application's GeoIP service.

    Async so FastAPI resolves it on the event loop rather than dispatching a
    plain attribute read to its thread pool.
    """
    return request.state.geoip


async def get_rdns(request: Request) -> ReverseDNSService:
    """Dependency: the application's reverse DNS service."""
    return request.state.rdns


GeoIP = Annotated[GeoIPService, Depends(get_geoip)]
ReverseDNS = Annotated[ReverseDNSService, Depends(get_rdns)]


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

app.include_router(fonts_router)


@app.get("/", response_class=HTMLResponse)
async def dashboard(geoip: GeoIP, rdns: ReverseDNS) -> str:
    """Render the main dashboard page with enriched source data."""
    chrony_data = await asyncio.to_thread(fetch_chrony_data)

    # Enrich sources with geo and hostname data if we have sources
    enriched_sources = None
    if chrony_data.sources:
        enriched_sources = await enrich_sources(chrony_data.sources, geoip, rdns)

    return str(
        dashboard_page(
            version=__version__,
            chrony_data=chrony_data,
            enriched_sources=enriched_sources,
            refresh_interval=get_settings().refresh_interval,
        )
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


# response_model is explicit because the 503 path returns a JSONResponse, and
# FastAPI cannot derive a model from a union that includes a Response.
@app.get(
    "/api/sources",
    response_model=SourcesResponse,
    responses={503: {"model": ApiError, "description": "chronyd is unreachable"}},
)
async def api_sources(geoip: GeoIP, rdns: ReverseDNS) -> SourcesResponse | JSONResponse:
    """Get enriched NTP sources as JSON for real-time updates.

    Returns all NTP sources with enriched display data including
    geolocation information and resolved hostnames.

    Returns:
        JSON response with sources, timestamp, sync status, and refresh interval.
        Returns 503 if unable to connect to chronyd.
    """
    chrony_data = await asyncio.to_thread(fetch_chrony_data)

    if chrony_data.error:
        return JSONResponse(
            status_code=503,
            content=ApiError(
                error="connection_failed", message=chrony_data.error
            ).model_dump(),
        )

    return SourcesResponse.build(
        await enrich_sources(chrony_data.sources, geoip, rdns),
        is_synchronized=chrony_data.is_synchronized,
        refresh_interval=get_settings().refresh_interval,
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
    settings = get_settings()
    uvicorn.run(
        "second_hand.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
