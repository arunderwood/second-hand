"""The /api/clients contract and its reflection on the dashboard page.

Covers the three response classes (404 absent, 200 unavailable, 200 ok), the
FR-021 address redaction, and truncation reporting. The availability ladder
itself is tested in test_clients_service.py; here it is mocked at the state
boundary.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from second_hand.clients_model import ReaderSnapshot
from second_hand.config import Settings
from second_hand.main import app, get_rdns
from second_hand.services.chrony import ChronyData
from second_hand.services.clients import READER_NOT_RUNNING, ClientsState
from second_hand.services.rdns import ReverseDNSResult
from tests.unit.test_clients_model import make_record, make_snapshot


class FakeRdns:
    """Answers batch lookups from a fixed name map and counts the calls."""

    def __init__(self, names: dict[str, str] | None = None) -> None:
        self.names = names or {}
        self.calls = 0

    async def batch_lookup(self, ips: list[str]) -> dict[str, ReverseDNSResult]:
        self.calls += 1
        return {
            ip: ReverseDNSResult(ip_address=ip, hostname=self.names.get(ip))
            for ip in ips
        }


def ok_state(**snapshot_overrides: object) -> ClientsState:
    snapshot = ReaderSnapshot.model_validate(make_snapshot(**snapshot_overrides))
    return ClientsState(
        status="ok",
        reason=None,
        reason_detail=None,
        snapshot=snapshot,
        age_seconds=7,
        stale=False,
    )


def unavailable_state(
    reason: str = READER_NOT_RUNNING, detail: str = "no data yet"
) -> ClientsState:
    return ClientsState(
        status="unavailable",
        reason=reason,
        reason_detail=detail,
        snapshot=None,
        age_seconds=None,
        stale=False,
    )


DISCONNECTED = ChronyData(
    tracking=None, sources=[], source_stats=[], rtc=None, error=None
)


@contextmanager
def serving(
    state: ClientsState | None,
    settings: Settings | None = None,
    rdns: FakeRdns | None = None,
) -> Iterator[TestClient]:
    """A client whose availability ladder answers ``state``."""
    if rdns is not None:
        app.dependency_overrides[get_rdns] = lambda: rdns
    try:
        with (
            patch("second_hand.main.get_clients_state", return_value=state),
            patch("second_hand.main.get_settings", return_value=settings or Settings()),
            patch("second_hand.main.fetch_chrony_data", return_value=DISCONNECTED),
            TestClient(app) as client,
        ):
            yield client
    finally:
        if rdns is not None:
            app.dependency_overrides.pop(get_rdns, None)


@pytest.fixture
def table_off_settings() -> Settings:
    return Settings(clients_table=False)


class TestResponseClasses:
    def test_absent_is_404(self) -> None:
        """Off or remote: the route answers as if it did not exist."""
        with serving(None) as client:
            assert client.get("/api/clients").status_code == 404

    def test_absent_page_has_no_panel(self) -> None:
        with serving(None) as client:
            page = client.get("/").text
        assert "clients-section" not in page
        assert "NTP Clients" not in page

    def test_unavailable_is_200_with_reason(self) -> None:
        """Unavailable is content, not an error (FR-017)."""
        with serving(unavailable_state()) as client:
            response = client.get("/api/clients")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "unavailable"
        assert body["reason"] == READER_NOT_RUNNING
        assert body["reason_detail"] == "no data yet"
        assert body["summary"] is None
        assert body["clients"] == []

    def test_reader_reason_passes_through(self) -> None:
        with serving(
            unavailable_state(reason="chrony_too_old", detail="chrony 3.4")
        ) as client:
            body = client.get("/api/clients").json()
        assert body["reason"] == "chrony_too_old"

    def test_ok_carries_data_and_display_strings(self) -> None:
        with serving(ok_state()) as client:
            body = client.get("/api/clients").json()
        assert body["status"] == "ok"
        assert body["summary"]["total_clients"] == 2
        assert body["totals"]["ntp_received"] == 100
        assert body["age_seconds"] == 7
        assert body["stale"] is False
        assert body["refresh_interval"] == 30
        (client_out,) = body["clients"]
        assert client_out["address"] == "192.0.2.17"
        assert client_out["poll_display"] == "1m 4s"
        assert client_out["last_seen_display"] == "12s ago"
        assert client_out["nts_ke_display"] == "—"

    def test_stale_state_surfaces(self) -> None:
        state = ok_state()
        state.stale = True
        state.age_seconds = 120
        with serving(state) as client:
            body = client.get("/api/clients").json()
        assert body["stale"] is True
        assert body["age_seconds"] == 120


class TestTableRedaction:
    """FR-021: with the table off, no client address leaves the server."""

    def test_api_has_aggregates_but_no_addresses(
        self, table_off_settings: Settings
    ) -> None:
        with serving(ok_state(), table_off_settings) as client:
            response = client.get("/api/clients")
        assert "192.0.2.17" not in response.text
        body = response.json()
        assert body["table_enabled"] is False
        assert body["clients"] == []
        assert body["clients_truncated"] == 0
        assert body["summary"]["total_clients"] == 2
        assert body["totals"]["ntp_received"] == 100

    def test_page_has_aggregates_but_no_addresses(
        self, table_off_settings: Settings
    ) -> None:
        with serving(ok_state(), table_off_settings) as client:
            page = client.get("/").text
        assert "192.0.2.17" not in page
        assert "clients-table" not in page
        assert "NTP Clients" in page

    def test_truncation_reported_when_table_on(self) -> None:
        with serving(ok_state(clients_truncated=42)) as client:
            body = client.get("/api/clients").json()
        assert body["clients_truncated"] == 42


class TestReverseDns:
    """FR-009: local reverse DNS names displayed clients, nothing else does."""

    def test_names_applied_to_api_and_page(self) -> None:
        rdns = FakeRdns({"192.0.2.17": "camera.lan"})
        with serving(ok_state(), rdns=rdns) as client:
            body = client.get("/api/clients").json()
            page = client.get("/").text
        (client_out,) = body["clients"]
        assert client_out["hostname"] == "camera.lan"
        assert client_out["display_name"] == "camera.lan"
        assert client_out["address"] == "192.0.2.17"
        # The page shows the name with the address as its title.
        assert 'title="192.0.2.17">camera.lan</span>' in page

    def test_unresolved_address_shows_bare(self) -> None:
        rdns = FakeRdns({})
        with serving(ok_state(), rdns=rdns) as client:
            (client_out,) = client.get("/api/clients").json()["clients"]
        assert client_out["hostname"] is None
        assert client_out["display_name"] == "192.0.2.17"

    def test_rdns_off_performs_no_lookups(self) -> None:
        """The off switch means no queries at all, not just hidden names."""
        rdns = FakeRdns({"192.0.2.17": "camera.lan"})
        with serving(ok_state(), Settings(clients_rdns=False), rdns=rdns) as client:
            body = client.get("/api/clients").json()
            client.get("/")
        assert rdns.calls == 0
        assert body["clients"][0]["display_name"] == "192.0.2.17"

    def test_table_off_performs_no_lookups(self) -> None:
        """FR-021 redaction leaves nothing to resolve."""
        rdns = FakeRdns({"192.0.2.17": "camera.lan"})
        with serving(ok_state(), Settings(clients_table=False), rdns=rdns) as client:
            client.get("/api/clients")
        assert rdns.calls == 0

    def test_no_other_enrichment_joins_a_client(self) -> None:
        """No geolocation, flags, or any third-party data on client rows."""
        record = make_record(address="2001:db8::1")
        with serving(ok_state(clients=[record]), rdns=FakeRdns({})) as client:
            page = client.get("/").text
        assert (
            '<td class="client-address"><span class="source-name">2001:db8::1' in page
        )
        assert "country-flag" not in page.split("clients-table")[1]
