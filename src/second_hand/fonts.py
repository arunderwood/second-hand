"""Serve the dashboard's web fonts from the distro's font packages.

The .deb Recommends ``fonts-jetbrains-mono`` and Suggests ``fonts-ibm-plex``
(only Suggests: Debian ships it in contrib, and a main package may not
Recommend outside main), so apt keeps the font files current and nothing is
vendored or fetched from a CDN. Where a package is absent (a dev machine, a pip
install, Debian without contrib) its routes 404 and style.css falls through to
the system font stacks.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from second_hand.config import get_settings

__all__ = ["FONT_FILES", "router"]

# Only these files are served. The route maps names to paths itself so a
# request can never select an arbitrary file under the fonts directory.
FONT_FILES: dict[str, str] = {
    "jetbrains-mono-400.ttf": "jetbrains-mono/JetBrainsMono-Regular.ttf",
    "jetbrains-mono-500.ttf": "jetbrains-mono/JetBrainsMono-Medium.ttf",
    "jetbrains-mono-600.ttf": "jetbrains-mono/JetBrainsMono-SemiBold.ttf",
    "jetbrains-mono-700.ttf": "jetbrains-mono/JetBrainsMono-Bold.ttf",
    "ibm-plex-sans-400.ttf": "ibm-plex/IBMPlexSans-Regular.ttf",
    "ibm-plex-sans-500.ttf": "ibm-plex/IBMPlexSans-Medium.ttf",
    "ibm-plex-sans-600.ttf": "ibm-plex/IBMPlexSans-SemiBold.ttf",
}

# A week: the files change only when apt upgrades the font package.
_CACHE_CONTROL = "public, max-age=604800"

router = APIRouter()


@router.get("/fonts/{name}", include_in_schema=False)
async def font(name: str) -> FileResponse:
    """Serve one allowlisted font file, or 404 if it is not installed."""
    relative = FONT_FILES.get(name)
    if relative is None:
        raise HTTPException(status_code=404)
    path = get_settings().fonts_dir / relative
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(
        path, media_type="font/ttf", headers={"Cache-Control": _CACHE_CONTROL}
    )
