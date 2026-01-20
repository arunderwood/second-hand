"""FastAPI application entry point for second-hand."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from second_hand import __version__
from second_hand.components import dashboard_page
from second_hand.components.base import error_page

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="second-hand",
    description="Chrony time statistics dashboard",
    version=__version__,
)

# Mount static files if directory exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    """Render the main dashboard page."""
    return str(dashboard_page(version=__version__))


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


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
