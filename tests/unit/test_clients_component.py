"""Renderings of the Clients panel: data, zero, unavailable, stale, log-full."""

import re

from second_hand.clients_model import ReaderSnapshot
from second_hand.components.clients import bucket_bar, clients_section
from second_hand.schemas import ClientsResponse
from second_hand.services.clients import READER_NOT_INSTALLED, ClientsState
from tests.unit.test_clients_model import make_record, make_snapshot, make_summary


def tag_with_class(html: str, css_class: str) -> str:
    """The opening tag that carries ``css_class``."""
    match = re.search(rf"<[a-z]+[^>]*{re.escape(css_class)}[^>]*>", html)
    assert match is not None, f"no element with class {css_class}"
    return match.group(0)


def render(
    *,
    state_status: str = "ok",
    reason: str | None = None,
    reason_detail: str | None = None,
    age_seconds: int | None = 7,
    stale: bool = False,
    table_enabled: bool = True,
    **snapshot_overrides: object,
) -> str:
    snapshot = (
        ReaderSnapshot.model_validate(make_snapshot(**snapshot_overrides))
        if state_status in ("ok",) or snapshot_overrides
        else None
    )
    state = ClientsState(
        status=state_status,  # type: ignore[arg-type]
        reason=reason,
        reason_detail=reason_detail,
        snapshot=snapshot if state_status == "ok" else None,
        age_seconds=age_seconds if state_status == "ok" else None,
        stale=stale,
    )
    response = ClientsResponse.build(
        state, table_enabled=table_enabled, refresh_interval=30
    )
    return str(clients_section(response))


class TestDataState:
    def test_aggregates_and_table(self) -> None:
        html = render()
        assert "NTP Clients" in html
        assert 'data-clients-field="total_clients">2<' in html
        assert 'data-clients-field="nts_split">1 / 1<' in html
        assert "192.0.2.17" in html
        assert "updated 7s ago" in html

    def test_table_columns_show_display_values(self) -> None:
        html = render(
            clients=[
                make_record(
                    ntp_interval=None, nts_ke_hits=3, is_nts=True, last_seen_seconds=65
                )
            ]
        )
        assert ">unknown<" in html
        assert ">1m 5s ago<" in html
        assert '<td class="client-nts-ke">3</td>' in html

    def test_truncation_line(self) -> None:
        html = render(clients_truncated=5)
        assert "5 more clients beyond this list" in html
        assert "hidden" not in tag_with_class(html, "clients-more")

    def test_no_truncation_line_hidden(self) -> None:
        html = render(clients_truncated=0)
        assert "hidden" in tag_with_class(html, "clients-more")

    def test_hostname_shows_with_address_title(self) -> None:
        """A named client reads as its name; the address stays as the title."""
        snapshot = ReaderSnapshot.model_validate(make_snapshot())
        state = ClientsState(
            status="ok",
            reason=None,
            reason_detail=None,
            snapshot=snapshot,
            age_seconds=7,
            stale=False,
        )
        response = ClientsResponse.build(state, table_enabled=True, refresh_interval=30)
        response.clients[0].apply_hostname("nas.lan")
        html = str(clients_section(response))
        assert 'title="192.0.2.17">nas.lan</span>' in html

    def test_table_absent_when_disabled(self) -> None:
        html = render(table_enabled=False)
        assert "clients-table-wrap" not in html
        assert "192.0.2.17" not in html
        assert 'data-clients-field="total_clients">2<' in html


class TestZeroState:
    def test_zero_clients_hint_visible(self) -> None:
        summary = make_summary(
            total_clients=0,
            nts_clients=0,
            ntp_clients=0,
            last_seen_buckets={"1m": 0, "1h": 0, "1d": 0, "older": 0},
        )
        html = render(summary=summary, clients=[])
        assert "hidden" not in tag_with_class(html, "clients-zero-hint")
        assert "chronyd only serves clients its configuration allows" in html

    def test_nonzero_hides_hint(self) -> None:
        html = render()
        assert "hidden" in tag_with_class(html, "clients-zero-hint")


class TestUnavailableState:
    def test_reason_line(self) -> None:
        html = render(
            state_status="unavailable",
            reason=READER_NOT_INSTALLED,
            reason_detail="only ships in the .deb",
        )
        assert "Client data unavailable" in html
        assert "reader is not installed" in html
        assert "(only ships in the .deb)" in html
        assert "stat-box" not in html
        assert "clients-table" not in html

    def test_unknown_reason_still_renders(self) -> None:
        html = render(state_status="unavailable", reason="mystery")
        assert "Client data unavailable" in html


class TestStaleState:
    def test_stale_badge_shown(self) -> None:
        html = render(stale=True, age_seconds=120)
        assert "hidden" not in tag_with_class(html, "clients-stale-badge")
        assert "updated 2m 0s ago" in html

    def test_fresh_badge_hidden(self) -> None:
        html = render(stale=False)
        assert "hidden" in tag_with_class(html, "clients-stale-badge")


class TestLogFullState:
    def test_rolling_window_note(self) -> None:
        totals = {
            "ntp_received": 100,
            "ntp_dropped": 0,
            "cmd_received": 5,
            "cmd_dropped": 0,
            "log_records_dropped": 17,
            "nts_ke_accepted": 0,
            "nts_ke_dropped": 0,
            "ntp_authenticated": 0,
            "ntp_interleaved": 0,
        }
        html = render(totals=totals)
        assert "hidden" not in tag_with_class(html, "clients-rolling-note")
        assert "not a complete census" in html

    def test_note_hidden_when_log_not_full(self) -> None:
        html = render()
        assert "hidden" in tag_with_class(html, "clients-rolling-note")


class TestBucketBars:
    def test_scaling(self) -> None:
        assert bucket_bar(0, 10) == "░" * 10
        assert bucket_bar(10, 10) == "█" * 10
        assert bucket_bar(5, 10) == "█" * 5 + "░" * 5
        # Any non-zero count shows at least one cell.
        assert bucket_bar(1, 1000).startswith("█")

    def test_bars_rendered_for_both_groups(self) -> None:
        html = render()
        assert 'data-bucket-group="last_seen" data-bucket="1m"' in html
        assert 'data-bucket-group="poll_interval" data-bucket="&lt;=64s"' in html
