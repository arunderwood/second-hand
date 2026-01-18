"""Tests for htpy components."""

from second_hand.components.base import base_layout, error_page
from second_hand.components.dashboard import dashboard_page


class TestBaseLayout:
    """Tests for base layout component."""

    def test_base_layout_includes_title(self) -> None:
        """Base layout should include the page title."""
        from htpy import p

        page = base_layout("Test Page", p["content"])
        html = str(page)
        assert "<title>Test Page</title>" in html

    def test_base_layout_includes_charset(self) -> None:
        """Base layout should declare UTF-8 charset."""
        from htpy import p

        page = base_layout("Test", p["test"])
        html = str(page)
        assert 'charset="utf-8"' in html

    def test_base_layout_includes_viewport(self) -> None:
        """Base layout should include responsive viewport meta tag."""
        from htpy import p

        page = base_layout("Test", p["test"])
        html = str(page)
        assert "viewport" in html
        assert "width=device-width" in html

    def test_base_layout_links_stylesheet(self) -> None:
        """Base layout should link to the CSS stylesheet."""
        from htpy import p

        page = base_layout("Test", p["test"])
        html = str(page)
        assert "/static/css/style.css" in html


class TestErrorPage:
    """Tests for error page component."""

    def test_error_page_displays_code(self) -> None:
        """Error page should display the error code."""
        page = error_page(code=404, message="Not found")
        html = str(page)
        assert "404" in html

    def test_error_page_displays_message(self) -> None:
        """Error page should display the error message."""
        page = error_page(code=500, message="Server error")
        html = str(page)
        assert "Server error" in html


class TestDashboardPage:
    """Tests for dashboard page component."""

    def test_dashboard_page_contains_version(self) -> None:
        """Dashboard page should display the application version."""
        page = dashboard_page(version="1.2.3")
        html = str(page)
        assert "1.2.3" in html

    def test_dashboard_page_has_title(self) -> None:
        """Dashboard page should have the correct title."""
        page = dashboard_page(version="0.1.0")
        html = str(page)
        assert "second-hand" in html

    def test_dashboard_page_has_placeholder_message(self) -> None:
        """Dashboard page should show placeholder for chrony stats."""
        page = dashboard_page(version="0.1.0")
        html = str(page)
        assert "chrony" in html.lower() or "time statistics" in html.lower()

    def test_dashboard_page_is_valid_html(self) -> None:
        """Dashboard page should be valid HTML structure."""
        page = dashboard_page(version="0.1.0")
        html = str(page)
        assert "<html" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html
