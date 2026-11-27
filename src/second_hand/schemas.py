"""Response models for the JSON API."""

import time
from typing import Literal, Self

from pydantic import BaseModel

from second_hand.clients_model import ClientRecord, ClientSummary, ServerTotals
from second_hand.presentation import (
    mode_display,
    reachability_percent,
    source_state_class,
    state_label,
)
from second_hand.services.chrony import EnrichedSource
from second_hand.services.clients import ClientsState
from second_hand.utils import (
    format_duration,
    format_offset,
    format_poll_interval,
    format_reachability_visual,
)

__all__ = ["ApiError", "ClientOut", "ClientsResponse", "SourceOut", "SourcesResponse"]


class SourceOut(BaseModel):
    """One NTP source, with display values the dashboard applies as-is."""

    address: str
    display_name: str
    # None when display_name fell back to the address.
    hostname: str | None
    country_code: str | None
    country_name: str | None
    country_flag: str
    mode: str
    mode_raw: str
    state: str
    is_selected: bool
    row_class: str | None
    stratum: int
    # Seconds. Float because chrony allows negative poll exponents (2**-2).
    poll: float
    poll_exponent: int
    reachability: int
    # Newest poll first, the reverse of the table's left-to-right order.
    reachability_bits: list[bool]
    reachability_percent: int
    last_rx: int
    last_rx_timestamp: int
    latest_meas: float
    latest_meas_display: str
    latest_meas_err: float
    latest_meas_err_display: str

    @classmethod
    def from_enriched(cls, es: EnrichedSource, now: float) -> Self:
        """Build the API view of a source as of ``now`` (epoch seconds)."""
        source = es.source
        return cls(
            address=source.address,
            display_name=es.display_name,
            hostname=es.hostname,
            country_code=es.country_code,
            country_name=es.country_name,
            country_flag=es.country_flag,
            mode=mode_display(source.mode.name).css_class,
            mode_raw=source.mode.name,
            state=state_label(source.state.name),
            is_selected=source.state.name == "SELECTED",
            row_class=source_state_class(source),
            stratum=source.stratum,
            poll=2**source.poll,
            poll_exponent=source.poll,
            reachability=source.reachability,
            reachability_bits=format_reachability_visual(source.reachability)[::-1],
            reachability_percent=reachability_percent(source.reachability),
            last_rx=source.last_sample_ago,
            last_rx_timestamp=int(now - source.last_sample_ago),
            latest_meas=source.latest_meas,
            latest_meas_display=format_offset(source.latest_meas),
            latest_meas_err=source.latest_meas_err,
            latest_meas_err_display=format_offset(source.latest_meas_err),
        )


class SourcesResponse(BaseModel):
    """Body of a successful ``GET /api/sources``."""

    sources: list[SourceOut]
    timestamp: int
    is_synchronized: bool
    refresh_interval: int

    @classmethod
    def build(
        cls,
        sources: list[EnrichedSource],
        *,
        is_synchronized: bool,
        refresh_interval: int,
    ) -> Self:
        """Snapshot ``sources`` against a single clock reading."""
        now = int(time.time())
        return cls(
            sources=[SourceOut.from_enriched(es, now) for es in sources],
            timestamp=now,
            is_synchronized=is_synchronized,
            refresh_interval=refresh_interval,
        )


class ClientOut(ClientRecord):
    """A client record with its display strings precomputed.

    The server's formatting rules are the only ones: dashboard.js writes these
    strings into cells as-is, exactly like the sources table.
    """

    poll_display: str
    last_seen_display: str
    nts_ke_display: str

    @classmethod
    def from_record(cls, record: ClientRecord) -> Self:
        return cls(
            **dict(record),
            poll_display=format_poll_interval(record.ntp_interval),
            last_seen_display=f"{format_duration(record.last_seen_seconds)} ago",
            # NTS-KE connections are shown where present (FR-005).
            nts_ke_display=(str(record.nts_ke_hits) if record.nts_ke_hits > 0 else "—"),
        )


class ClientsResponse(BaseModel):
    """Body of ``GET /api/clients``; the panel renders from the same build.

    ``reason`` is the reader's enum plus the two dashboard-side values
    ``reader_not_installed`` and ``reader_not_running``.
    """

    status: Literal["ok", "unavailable"]
    reason: str | None
    reason_detail: str | None
    taken_at: int | None
    age_seconds: int | None
    stale: bool
    summary: ClientSummary | None
    totals: ServerTotals | None
    table_enabled: bool
    clients: list[ClientOut]
    clients_truncated: int
    refresh_interval: int

    @classmethod
    def build(
        cls,
        state: ClientsState,
        *,
        table_enabled: bool,
        refresh_interval: int,
    ) -> Self:
        """Wrap an availability state with what only the dashboard knows.

        FR-021 is enforced right here, at the serialization boundary: with the
        table off, no client record — and so no client address — ever leaves
        the server, on this response or the page rendered from it.
        """
        snapshot = state.snapshot
        include_clients = table_enabled and snapshot is not None
        return cls(
            status=state.status,
            reason=state.reason,
            reason_detail=state.reason_detail,
            taken_at=snapshot.taken_at if snapshot else None,
            age_seconds=state.age_seconds,
            stale=state.stale,
            summary=snapshot.summary if snapshot else None,
            totals=snapshot.totals if snapshot else None,
            table_enabled=table_enabled,
            clients=(
                [ClientOut.from_record(record) for record in snapshot.clients]
                if include_clients and snapshot
                else []
            ),
            clients_truncated=(
                snapshot.clients_truncated if include_clients and snapshot else 0
            ),
            refresh_interval=refresh_interval,
        )


class ApiError(BaseModel):
    """Body of an API error response."""

    error: str
    message: str
