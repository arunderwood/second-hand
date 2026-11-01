"""Tests for serving fonts from the distro font packages."""

import re
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from second_hand.config import get_settings
from second_hand.fonts import FONT_FILES
from second_hand.main import STATIC_DIR, app


@pytest.fixture
def fonts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path]:
    """Point the app at a fake fonts tree holding every allowlisted file."""
    for relative in FONT_FILES.values():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\0\1\0\0 fake ttf")
    (tmp_path / "secret.txt").write_text("not a font")

    monkeypatch.setenv("SECOND_HAND_FONTS_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


class TestFontRoute:
    def test_serves_allowlisted_font(self, fonts_dir: Path) -> None:
        with TestClient(app) as client:
            response = client.get("/fonts/jetbrains-mono-400.ttf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "font/ttf"
        assert "max-age" in response.headers["cache-control"]
        assert response.content == b"\0\1\0\0 fake ttf"

    @pytest.mark.parametrize(
        "name", ["secret.txt", "..%2Fsecret.txt", "JetBrainsMono-Regular.ttf"]
    )
    def test_rejects_names_outside_the_allowlist(
        self, fonts_dir: Path, name: str
    ) -> None:
        with TestClient(app) as client:
            assert client.get(f"/fonts/{name}").status_code == 404

    def test_missing_package_is_a_404(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without the font packages the CSS falls back to system fonts."""
        monkeypatch.setenv("SECOND_HAND_FONTS_DIR", str(tmp_path))
        get_settings.cache_clear()
        try:
            with TestClient(app) as client:
                assert client.get("/fonts/ibm-plex-sans-400.ttf").status_code == 404
        finally:
            get_settings.cache_clear()


class TestStylesheetFonts:
    def test_every_font_url_in_css_is_served(self) -> None:
        """A @font-face URL the route does not know would silently 404."""
        css = (STATIC_DIR / "css" / "style.css").read_text()
        urls = set(re.findall(r"url\('/fonts/([^']+)'\)", css))
        assert urls == set(FONT_FILES)

    def test_stylesheet_loads_nothing_third_party(self) -> None:
        css = (STATIC_DIR / "css" / "style.css").read_text()
        assert "https://" not in css
        assert "@import" not in css
