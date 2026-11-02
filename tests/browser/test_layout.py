"""Layout rules of the dashboard, measured in a real browser.

The other tests only see the HTML, which says nothing about whether a value fits
its box. These render the real app and stylesheet at widths across the range of
phones to large monitors. They need the ``browser`` dependency group:

    uv sync --group browser
    uv run playwright install chromium firefox webkit
    LAYOUT_BROWSER=webkit uv run pytest tests/browser

``LAYOUT_BROWSER`` defaults to chromium; CI runs all three.
"""

import importlib
import os
import socket
import threading
import time
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import httpx2
import pytest
import uvicorn
from pychrony.testing import (
    make_rtc_data,
    make_source,
    make_source_stats,
    make_tracking,
)

from second_hand.main import app, get_geoip
from second_hand.services.chrony import ChronyData
from second_hand.services.geoip import GeoIPService

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page

# Skips where the group isn't installed, but not in CI, where a skip would pass a
# job that checked nothing.
sync_api = (
    importlib.import_module("playwright.sync_api")
    if os.environ.get("CI")
    else pytest.importorskip("playwright.sync_api")
)

BROWSER = os.environ.get("LAYOUT_BROWSER", "chromium")
# Uploaded by CI when a run fails.
SCREENSHOTS = Path("test-results")

# Both sides of every breakpoint in style.css, as well as an even sweep.
WIDTHS = sorted({*range(320, 2601, 40), 768, 769, 1024, 1025, 1919, 1920})
TOOLTIP_WIDTHS = [390, 800, 1024, 1025, 1280, 1920]

TYPICAL = ChronyData(
    tracking=make_tracking(),
    sources=[make_source(address="192.0.2.5") for _ in range(3)],
    source_stats=[make_source_stats() for _ in range(3)],
    rtc=make_rtc_data(),
    error=None,
)
# The Reference value is longer than chrony sends today, so that a pass doesn't
# depend on it staying short. The address is the longest form of an IPv6 one.
LONG_VALUES = ChronyData(
    tracking=make_tracking(
        reference_id_name="time-a.timefreq.bldrdoc.gov",
        reference_ip="2001:0db8:85a3:0000:0000:8a2e:0370:7334",
    ),
    sources=[make_source(address="ntp-stratum2-cluster01.sea.isp.example.net")],
    source_stats=[make_source_stats()],
    rtc=make_rtc_data(),
    error=None,
)
UNAVAILABLE = ChronyData(
    tracking=None, sources=[], source_stats=[], rtc=None, error="Unable to connect"
)

# Text is measured with a Range because an element's own box stretches to its
# grid cell and so can't show the text escaping it.
_FIND_OVERFLOW = """
() => {
  const problems = [];
  const root = document.documentElement;
  if (root.scrollWidth > root.clientWidth) {
    problems.push(`page ${root.scrollWidth - root.clientWidth}px too wide`);
  }
  const boxes = document.querySelectorAll('.stat-box, .rtc-stat');
  if (boxes.length === 0) {
    problems.push('no stat boxes to measure');
  }
  const range = document.createRange();
  for (const box of boxes) {
    const right = box.getBoundingClientRect().right;
    const title = box.querySelector('.stat-title, .rtc-stat-title');
    const value = box.querySelector('.stat-value, .rtc-stat-value');
    // The trigger's first child is its label; the rest is screen-reader text.
    const label = title.querySelector('.tooltip-trigger')?.firstChild ?? title;
    for (const text of [label, value]) {
      range.selectNodeContents(text);
      const excess = range.getBoundingClientRect().right - right;
      if (excess > 0.5) {
        problems.push(`"${text.textContent}" ${Math.round(excess)}px out of its box`);
      }
    }
  }
  return problems;
}
"""

_GRID_DISPLAY = "getComputedStyle(document.querySelector('.stats-grid')).display"

# A short row shows the grid's background as a solid block.
_FIND_SHORT_ROWS = """
() => {
  const problems = [];
  const grids = document.querySelectorAll('.stats-grid, .rtc-stats');
  if (grids.length === 0) {
    problems.push('no grids to measure');
  }
  for (const grid of grids) {
    const box = grid.getBoundingClientRect();
    const edge = box.left + grid.clientLeft + grid.clientWidth;
    const rowEnds = new Map();
    for (const cell of grid.children) {
      const rect = cell.getBoundingClientRect();
      const row = Math.round(rect.top);
      rowEnds.set(row, Math.max(rowEnds.get(row) ?? 0, rect.right));
    }
    for (const [row, end] of rowEnds) {
      if (end < edge - 1) {
        problems.push(`.${grid.className} row at y=${row} ends ${Math.round(edge - end)}px short`);
      }
    }
  }
  return problems;
}
"""

_REF_TIME_LINES = """
() => {
  const range = document.createRange();
  const value = [...document.querySelectorAll('.stat-value')]
    .find((element) => element.textContent.endsWith('UTC'));
  range.selectNodeContents(value);
  return new Set([...range.getClientRects()].map((r) => Math.round(r.top))).size;
}
"""

# A pseudo-element has no rect of its own. Its computed offsets resolve to pixels,
# relative to the viewport when fixed and to its trigger otherwise.
_FIND_OFFSCREEN_TOOLTIPS = """
() => {
  const problems = [];
  const root = document.documentElement;
  const triggers = document.querySelectorAll('.tooltip-trigger[data-tooltip]');
  if (triggers.length === 0) {
    problems.push('no tooltips to open');
  }
  for (const trigger of triggers) {
    trigger.focus();
    const name = trigger.firstChild.textContent;
    const style = getComputedStyle(trigger, '::after');
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
      problems.push(`"${name}" tooltip didn't appear`);
    }
    const origin = style.position === 'fixed' ? 0 : trigger.getBoundingClientRect().left;
    const left = origin + parseFloat(style.left);
    const right = left + parseFloat(style.width);
    if (left < 0 || right > root.clientWidth) {
      problems.push(`"${name}" tooltip spans ${Math.round(left)}-${Math.round(right)}px`);
    }
    if (root.scrollWidth > root.clientWidth) {
      problems.push(`"${name}" tooltip widens the page`);
    }
    trigger.blur();
  }
  return problems;
}
"""


@pytest.fixture(scope="module")
def server_url() -> Generator[str, None, None]:
    """Serve the real app, so the stylesheet arrives under its real headers."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    thread = threading.Thread(target=server.run, args=([sock],), daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            pytest.fail("the app never started, so there is no page to measure")
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}/"
    finally:
        server.should_exit = True
        thread.join()


@pytest.fixture(scope="module")
def browser() -> Generator["Browser", None, None]:
    """A browser that can't launch is an error, never a skip."""
    with sync_api.sync_playwright() as playwright:
        browser = getattr(playwright, BROWSER).launch()
        yield browser
        browser.close()


@pytest.fixture
def offline_geoip() -> Generator[None, None, None]:
    """Keep source enrichment away from ipwho.is."""
    transport = httpx2.MockTransport(lambda _: httpx2.Response(404))
    service = GeoIPService(httpx2.AsyncClient(transport=transport))
    app.dependency_overrides[get_geoip] = lambda: service
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_geoip, None)


@contextmanager
def open_dashboard(
    browser: "Browser", url: str, data: ChronyData, **page_options: Any
) -> Iterator["Page"]:
    """Load the dashboard showing ``data``, with its web fonts settled."""
    with patch("second_hand.main.fetch_chrony_data", return_value=data):
        page = browser.new_page(**page_options)
        try:
            response = page.goto(url)
            assert response is not None and response.ok
            # An unstyled page has nothing overflowing, and would pass every check.
            assert page.evaluate(_GRID_DISPLAY) == "grid", "stylesheet didn't apply"
            page.evaluate("document.fonts.ready.then(() => {})")
            yield page
        finally:
            page.close()


def problems_by_width(
    page: "Page", script: str, widths: list[int], request: pytest.FixtureRequest
) -> dict[int, list[Any]]:
    """Run ``script`` at each width, keeping only the widths it complains about.

    The first such width also leaves a screenshot, for a failure in CI.
    """
    found: dict[int, list[Any]] = {}
    for width in widths:
        page.set_viewport_size({"width": width, "height": 900})
        if problems := page.evaluate(script):
            if not found:
                path = SCREENSHOTS / f"{BROWSER}-{request.node.name}-{width}px.png"
                page.screenshot(path=path, full_page=True)
            found[width] = problems
    return found


@pytest.fixture(
    params=[TYPICAL, LONG_VALUES, UNAVAILABLE],
    ids=["typical", "long-values", "chrony-unavailable"],
)
def dashboard(
    request: pytest.FixtureRequest,
    browser: "Browser",
    server_url: str,
    offline_geoip: None,
) -> Generator["Page", None, None]:
    """The dashboard, once for each kind of data that stresses the layout."""
    with open_dashboard(browser, server_url, request.param) as page:
        yield page


def test_nothing_overflows(dashboard: "Page", request: pytest.FixtureRequest) -> None:
    """No value or label leaves its box, and the page never scrolls sideways."""
    assert problems_by_width(dashboard, _FIND_OVERFLOW, WIDTHS, request) == {}


def test_every_grid_row_is_full(
    dashboard: "Page", request: pytest.FixtureRequest
) -> None:
    """Box counts and column counts keep dividing evenly at every width."""
    assert problems_by_width(dashboard, _FIND_SHORT_ROWS, WIDTHS, request) == {}


def test_tooltips_stay_on_screen(
    dashboard: "Page", request: pytest.FixtureRequest
) -> None:
    """Every tooltip opens fully inside the window, without widening the page."""
    found = problems_by_width(
        dashboard, _FIND_OFFSCREEN_TOOLTIPS, TOOLTIP_WIDTHS, request
    )
    assert found == {}


def test_tapping_a_label_opens_its_tooltip(
    browser: "Browser", server_url: str, offline_geoip: None
) -> None:
    """A phone has no hover, so a tap has to be enough on its own."""
    with open_dashboard(
        browser,
        server_url,
        TYPICAL,
        has_touch=True,
        viewport={"width": 390, "height": 844},
    ) as page:
        page.tap(".tooltip-trigger")
        display = "getComputedStyle(document.activeElement, '::after').display"
        assert page.evaluate(display) == "block"


def test_ref_time_stays_on_one_line(
    browser: "Browser", server_url: str, offline_geoip: None
) -> None:
    """With ordinary values, the timestamp never needs its wrapping fallback."""
    with open_dashboard(browser, server_url, TYPICAL) as page:
        for width in WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            assert page.evaluate(_REF_TIME_LINES) == 1, f"wrapped at {width}px"
