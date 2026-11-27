"""Shared models for chronyd client visibility.

Both processes import this module: the reader serializes a ``ReaderSnapshot``
to the snapshot file, and the dashboard deserializes and validates it.
Untrusted-input discipline applies even to a local file — a malformed snapshot
must degrade to the unavailable state, never a 500 — so every constraint the
dashboard relies on is enforced here, not at the call sites.
"""

import ipaddress
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, Field, NonNegativeInt, field_validator, model_validator

__all__ = [
    "LAST_SEEN_BUCKETS",
    "POLL_INTERVAL_BUCKETS",
    "SCHEMA_VERSION",
    "ClientRecord",
    "ClientSummary",
    "ReaderSnapshot",
    "ServerTotals",
    "UnavailableReason",
]

SCHEMA_VERSION = 1


class UnavailableReason(StrEnum):
    """Why the reader could not produce client data (FR-017)."""

    CHRONY_TOO_OLD = "chrony_too_old"
    CLIENT_LOGGING_DISABLED = "client_logging_disabled"
    CHRONYD_UNREACHABLE = "chronyd_unreachable"
    PERMISSION_DENIED = "permission_denied"
    PARSE_ERROR = "parse_error"


class LastSeenBucket(StrEnum):
    """How recently a client was last seen (FR-002)."""

    LAST_MINUTE = "1m"
    LAST_HOUR = "1h"
    LAST_DAY = "1d"
    OLDER = "older"


class PollIntervalBucket(StrEnum):
    """How often a client polls (FR-002). ASCII keys, exactly as in the JSON."""

    FAST = "<=64s"
    NORMAL = "<=1024s"
    SLOW = ">1024s"
    UNKNOWN = "unknown"


# Ordered as the panel displays them; the enums keep API and panel agreeing.
LAST_SEEN_BUCKETS = tuple(LastSeenBucket)
POLL_INTERVAL_BUCKETS = tuple(PollIntervalBucket)


class ClientRecord(BaseModel):
    """One host from chronyd's client log that qualifies as a client.

    A client has NTP hits > 0 or NTS-KE hits > 0; monitoring-only rows are
    dropped before this model is built. Represents "recently seen", not
    "currently connected".
    """

    # Shown as-is: no hostname, geolocation, or other lookup (FR-009).
    address: str
    ntp_hits: NonNegativeInt
    ntp_drops: NonNegativeInt
    # log2 seconds (negative means sub-second), None = unknown. chronyc's CSV
    # sentinel for unknown is 127, which the parser must map to None here:
    # -1 cannot be the sentinel because 2**-1 is a real half-second interval.
    ntp_interval: int | None
    # Interval enforced after rate limiting, None = not limited.
    ntp_interval_limited: int | None
    last_ntp_seconds: NonNegativeInt | None
    nts_ke_hits: NonNegativeInt
    nts_ke_drops: NonNegativeInt
    last_nts_ke_seconds: NonNegativeInt | None
    is_nts: bool
    last_seen_seconds: NonNegativeInt

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Require an IPv4/IPv6 literal; anything else is not a client row."""
        ipaddress.ip_address(v)
        return v


class ClientSummary(BaseModel):
    """Aggregates over all qualifying records, not just the published top-N."""

    total_clients: NonNegativeInt
    nts_clients: NonNegativeInt
    ntp_clients: NonNegativeInt
    rate_limited_clients: NonNegativeInt
    total_dropped_requests: NonNegativeInt
    last_seen_buckets: dict[LastSeenBucket, NonNegativeInt]
    poll_interval_buckets: dict[PollIntervalBucket, NonNegativeInt]


class ServerTotals(BaseModel):
    """chronyd's server-wide counters since it started.

    They reset when chronyd restarts, which the panel shows as-is.
    """

    ntp_received: NonNegativeInt
    ntp_dropped: NonNegativeInt
    cmd_received: NonNegativeInt
    cmd_dropped: NonNegativeInt
    # Non-zero means the client log is full and counts are a rolling window,
    # which the panel must say (FR-007).
    log_records_dropped: NonNegativeInt
    nts_ke_accepted: NonNegativeInt
    nts_ke_dropped: NonNegativeInt
    ntp_authenticated: NonNegativeInt
    ntp_interleaved: NonNegativeInt


class ReaderSnapshot(BaseModel):
    """The document the reader publishes each cycle — the local channel.

    Fields may be added within schema version 1 (the parser ignores unknown
    JSON fields); removing or retyping one requires a version bump, which the
    dashboard rejects into the unavailable state.
    """

    schema_version: Literal[1]
    # Epoch seconds; staleness is computed against this (FR-018).
    taken_at: int
    # The reader's cycle in seconds; stale when age > 3 * interval.
    interval: int = Field(ge=1)
    status: Literal["ok", "unavailable"]
    reason: UnavailableReason | None = None
    reason_detail: str | None = None
    summary: ClientSummary | None = None
    totals: ServerTotals | None = None
    # Top max_rows by recency, most recently seen first; [] when unavailable.
    clients: list[ClientRecord] = []
    # Qualifying clients beyond the published cap (FR-006).
    clients_truncated: NonNegativeInt = 0

    @model_validator(mode="after")
    def validate_status_shape(self) -> Self:
        """An unavailable snapshot names its reason; an ok one carries data."""
        if self.status == "unavailable" and self.reason is None:
            raise ValueError("unavailable snapshot must carry a reason")
        if self.status == "ok" and (self.summary is None or self.totals is None):
            raise ValueError("ok snapshot must carry summary and totals")
        return self
