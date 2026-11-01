"""Tests for the /api/sources contract that dashboard.js consumes."""

import threading
from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pychrony import SourceMode, SourceState
from pychrony.testing import make_source, make_tracking

from second_hand.main import app
from second_hand.services.chrony import ChronyData

# Private addresses keep the GeoIP service off the network.
SOURCES = [
    make_source(
        address="192.168.1.1",
        mode=SourceMode.CLIENT,
        state=SourceState.SELECTED,
        reachability=0b0111_1111,
        poll=6,
        latest_meas=0.0012345,
        latest_meas_err=0.0000021,
    ),
    make_source(
        address="10.0.0.1",
        mode=SourceMode.PEER,
        state=SourceState.UNSELECTED,
        reachability=0,
    ),
]


def chrony_data(**overrides: object) -> ChronyData:
    """Connected chrony data with SOURCES, unless overridden."""
    fields: dict[str, object] = {
        "tracking": make_tracking(),
        "sources": SOURCES,
        "source_stats": [],
        "rtc": None,
        "error": None,
    }
    fields.update(overrides)
    return ChronyData(**fields)  # type: ignore[arg-type]


@pytest.fixture
def client() -> Generator[TestClient]:
    with (
        TestClient(app) as c,
        patch("second_hand.main.fetch_chrony_data", return_value=chrony_data()),
    ):
        yield c


class TestSourcesPayload:
    """Display values come from the server so the browser never re-derives them."""

    def test_sources_keep_chrony_order(self, client: TestClient) -> None:
        body = client.get("/api/sources").json()
        assert [s["address"] for s in body["sources"]] == ["192.168.1.1", "10.0.0.1"]

    def test_display_fields(self, client: TestClient) -> None:
        selected, unselected = client.get("/api/sources").json()["sources"]

        assert selected["mode"] == "server"
        assert selected["state"] == "Selected"
        assert selected["is_selected"] is True
        assert selected["row_class"] == "source-selected"
        assert selected["poll"] == 64
        assert selected["latest_meas_display"] == "+1.234 ms"
        assert selected["latest_meas_err_display"] == "+2.1 µs"

        assert unselected["mode"] == "peer"
        assert unselected["row_class"] == "source-unreachable"

    def test_reachability_bits_are_newest_first(self, client: TestClient) -> None:
        selected = client.get("/api/sources").json()["sources"][0]

        # 0b0111_1111: the seven most recent polls succeeded, the oldest failed.
        assert selected["reachability_bits"] == [True] * 7 + [False]
        assert selected["reachability_percent"] == 87

    def test_envelope(self, client: TestClient) -> None:
        body = client.get("/api/sources").json()

        assert body["refresh_interval"] == 30
        assert isinstance(body["timestamp"], int)
        assert isinstance(body["is_synchronized"], bool)


class TestChronydUnavailable:
    def test_returns_503_with_error_body(self) -> None:
        down = chrony_data(tracking=None, sources=[], error="Unable to connect")
        with (
            TestClient(app) as client,
            patch("second_hand.main.fetch_chrony_data", return_value=down),
        ):
            response = client.get("/api/sources")

        assert response.status_code == 503
        assert response.json() == {
            "error": "connection_failed",
            "message": "Unable to connect",
        }


class TestEventLoopIsNotBlocked:
    """chronyd is queried over a blocking socket, which must stay off the loop."""

    @pytest.mark.parametrize("path", ["/", "/api/sources"])
    def test_chrony_is_queried_from_a_worker_thread(self, path: str) -> None:
        loop_thread: list[threading.Thread] = []
        fetch_thread: list[threading.Thread] = []

        async def record_loop_thread() -> None:
            loop_thread.append(threading.current_thread())

        def fake_fetch() -> ChronyData:
            fetch_thread.append(threading.current_thread())
            return chrony_data()

        with (
            TestClient(app) as client,
            patch("second_hand.main.fetch_chrony_data", side_effect=fake_fetch),
        ):
            client.portal.call(record_loop_thread)  # type: ignore[union-attr]
            assert client.get(path).status_code == 200

        assert fetch_thread
        assert fetch_thread[0] is not loop_thread[0]
