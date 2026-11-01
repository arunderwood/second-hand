"""Response models for the JSON API."""

import time
from typing import Self

from pydantic import BaseModel

from second_hand.presentation import (
    mode_display,
    reachability_percent,
    source_state_class,
    state_label,
)
from second_hand.services.chrony import EnrichedSource
from second_hand.utils import format_offset, format_reachability_visual

__all__ = ["ApiError", "SourceOut", "SourcesResponse"]


class SourceOut(BaseModel):
    """One NTP source, with display values the dashboard applies as-is."""

    address: str
    display_name: str
    # None when the address has no PTR record. display_name already falls back
    # to the address; this is what tells the client whether it did.
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


class ApiError(BaseModel):
    """Body of an API error response."""

    error: str
    message: str
