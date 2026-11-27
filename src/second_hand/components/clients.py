"""Clients panel: who is getting time from this server.

Renders from the same ClientsResponse build the API serves, so page and API
cannot drift (contracts/api-clients.md). When the feature is off or chronyd is
remote the dashboard never calls this module: absence is decided upstream.
"""

from htpy import Element, div, h2, p, section, span, table, tbody, td, th, thead, tr

from second_hand.clients_model import (
    LAST_SEEN_BUCKETS,
    POLL_INTERVAL_BUCKETS,
    LastSeenBucket,
    PollIntervalBucket,
)
from second_hand.components.base import source_name
from second_hand.schemas import ClientOut, ClientsResponse
from second_hand.utils import format_duration

__all__ = ["clients_section"]

# One short, specific line per unavailability (FR-017).
REASON_TEXT = {
    "chrony_too_old": "The installed chrony version is too old for client data"
    " (4.0 or later is required).",
    "client_logging_disabled": "Client logging is turned off in chronyd.",
    "chronyd_unreachable": "chronyd is unreachable.",
    "permission_denied": "The reader was not authorised to query chronyd.",
    "parse_error": "chronyd's answer could not be parsed.",
    "reader_not_installed": "The client-data reader is not installed; it ships"
    " with the Debian package.",
    "reader_not_running": "The client-data reader is not running.",
}

_LAST_SEEN_LABELS = {
    LastSeenBucket.LAST_MINUTE: "last minute",
    LastSeenBucket.LAST_HOUR: "last hour",
    LastSeenBucket.LAST_DAY: "last day",
    LastSeenBucket.OLDER: "older",
}

_POLL_LABELS = {
    PollIntervalBucket.FAST: "≤ 64s",
    PollIntervalBucket.NORMAL: "≤ 1024s",
    PollIntervalBucket.SLOW: "> 1024s",
    PollIntervalBucket.UNKNOWN: "unknown",
}

# Text bars render under the strict CSP (style-src 'self' forbids the inline
# width styles a div-based bar would need), and dashboard.js can rebuild them
# as plain strings.
_BAR_CELLS = 10
_BAR_FULL = "█"
_BAR_EMPTY = "░"


def clients_section(data: ClientsResponse) -> Element:
    """The whole Clients panel for one response."""
    return section(".clients-section", data_status=data.status)[
        h2(".section-title")["NTP Clients"],
        _meta_line(data),
        _unavailable(data) if data.status == "unavailable" else _body(data),
    ]


def _meta_line(data: ClientsResponse) -> Element | None:
    """Data age, always shown, with a stale badge past the threshold (FR-018)."""
    if data.age_seconds is None:
        return None
    return div(".clients-meta")[
        span(
            ".clients-age",
            **{
                "data-clients-field": "age",
                "data-taken-at": str(data.taken_at or ""),
            },
        )[f"updated {format_duration(data.age_seconds)} ago"],
        span(".clients-stale-badge", hidden=not data.stale)["STALE"],
    ]


def _unavailable(data: ClientsResponse) -> Element:
    """Compact unavailable state; the rest of the dashboard is unaffected."""
    sentence = REASON_TEXT.get(data.reason or "", "Client data is unavailable.")
    detail = f" ({data.reason_detail})" if data.reason_detail else ""
    return p(".empty-message.clients-unavailable")[
        f"Client data unavailable: {sentence}{detail}"
    ]


def _body(data: ClientsResponse) -> list[Element | None]:
    assert data.summary is not None and data.totals is not None
    summary, totals = data.summary, data.totals
    return [
        # chronyd recycles its oldest log entries once full: from then on every
        # count is a rolling window, which the operator must be told (FR-007).
        div(
            ".clients-note.clients-rolling-note", hidden=totals.log_records_dropped == 0
        )[
            "chronyd's client log is full: these are recently seen clients, "
            "not a complete census, and counts can go down."
        ],
        div(".clients-note.clients-zero-hint", hidden=summary.total_clients != 0)[
            "No clients seen. chronyd only serves clients its configuration "
            "allows (see chrony.conf's allow directive)."
        ],
        _aggregates(data),
        div(".clients-buckets")[
            _bucket_group(
                "Last seen",
                "last_seen",
                {b: summary.last_seen_buckets.get(b, 0) for b in LAST_SEEN_BUCKETS},
                _LAST_SEEN_LABELS,
            ),
            _bucket_group(
                "Poll interval",
                "poll_interval",
                {
                    b: summary.poll_interval_buckets.get(b, 0)
                    for b in POLL_INTERVAL_BUCKETS
                },
                _POLL_LABELS,
            ),
        ],
        _totals_table(data),
        _clients_table(data) if data.table_enabled else None,
    ]


def _aggregates(data: ClientsResponse) -> Element:
    assert data.summary is not None
    summary = data.summary
    boxes = [
        ("Clients Seen", "total_clients", str(summary.total_clients)),
        ("NTS / NTP", "nts_split", f"{summary.nts_clients} / {summary.ntp_clients}"),
        (
            "Rate-limited",
            "rate_limited_clients",
            str(summary.rate_limited_clients),
        ),
        (
            "Dropped Requests",
            "total_dropped_requests",
            str(summary.total_dropped_requests),
        ),
    ]
    # Four boxes in a four-column grid (two on phones): every row stays full,
    # which the layout tests enforce.
    return div(".clients-grid")[
        (
            div(".stat-box")[
                div(".stat-title")[title],
                div(".stat-value", **{"data-clients-field": field})[value],
            ]
            for title, field, value in boxes
        )
    ]


def _bucket_group(
    title: str,
    group: str,
    counts: dict,
    labels: dict,
) -> Element:
    scale = max(counts.values(), default=0)
    return div(".bucket-group")[
        div(".bucket-group-title")[title],
        (
            div(".bucket-row")[
                span(".bucket-label")[labels[bucket]],
                span(
                    ".bucket-bar",
                    **{"data-bucket-group": group, "data-bucket": bucket.value},
                )[bucket_bar(count, scale)],
                span(
                    ".bucket-count",
                    **{
                        "data-bucket-group": f"{group}-count",
                        "data-bucket": bucket.value,
                    },
                )[str(count)],
            ]
            for bucket, count in counts.items()
        ),
    ]


def bucket_bar(count: int, scale: int) -> str:
    """A ten-cell text bar; any non-zero count shows at least one cell."""
    if scale <= 0 or count <= 0:
        return _BAR_EMPTY * _BAR_CELLS
    filled = max(1, round(count / scale * _BAR_CELLS))
    return _BAR_FULL * filled + _BAR_EMPTY * (_BAR_CELLS - filled)


def _totals_table(data: ClientsResponse) -> Element:
    """Server-wide counters since chronyd started (FR-004)."""
    assert data.totals is not None
    totals = data.totals
    rows = [
        ("NTP requests", totals.ntp_received, totals.ntp_dropped),
        ("Monitoring requests", totals.cmd_received, totals.cmd_dropped),
        ("NTS-KE connections", totals.nts_ke_accepted, totals.nts_ke_dropped),
    ]
    extras = [
        ("Authenticated NTP", "ntp_authenticated", totals.ntp_authenticated),
        ("Interleaved NTP", "ntp_interleaved", totals.ntp_interleaved),
        (
            "Client-log records dropped",
            "log_records_dropped",
            totals.log_records_dropped,
        ),
    ]
    field_names = {
        "NTP requests": ("ntp_received", "ntp_dropped"),
        "Monitoring requests": ("cmd_received", "cmd_dropped"),
        "NTS-KE connections": ("nts_ke_accepted", "nts_ke_dropped"),
    }
    return div(".clients-totals")[
        div(".bucket-group-title")["Server Totals (since chronyd started)"],
        div(".table-scroll")[
            table(".data-table.clients-totals-table")[
                thead[tr[th["Kind"], th["Received"], th["Dropped"]]],
                tbody[
                    (
                        tr[
                            td[kind],
                            td(**{"data-totals-field": field_names[kind][0]})[
                                str(received)
                            ],
                            td(**{"data-totals-field": field_names[kind][1]})[
                                str(dropped)
                            ],
                        ]
                        for kind, received, dropped in rows
                    )
                ],
            ],
        ],
        p(".clients-totals-extras")[
            (
                span(".totals-extra")[
                    f"{label}: ",
                    span(**{"data-totals-field": field})[str(value)],
                ]
                for label, field, value in extras
            )
        ],
    ]


def _clients_table(data: ClientsResponse) -> Element:
    """Per-client table, most recently seen first, capped (FR-005/FR-006)."""
    body: Element | str
    if data.clients:
        body = tbody(".clients-tbody")[(_client_row(record) for record in data.clients)]
    else:
        body = tbody(".clients-tbody")[
            tr[td(".clients-table-empty", colspan="6")["No clients to list"]]
        ]
    return div(".clients-table-wrap")[
        div(".bucket-group-title")["Recently Seen Clients"],
        div(".table-scroll")[
            table(".data-table.clients-table")[
                thead[
                    tr[
                        th["Address"],
                        th["NTP Requests"],
                        th["Dropped"],
                        th["Poll Interval"],
                        th["Last Seen"],
                        th["NTS-KE"],
                    ]
                ],
                body,
            ],
        ],
        p(
            ".clients-more",
            hidden=data.clients_truncated == 0,
            **{"data-clients-field": "truncated"},
        )[f"{data.clients_truncated} more clients beyond this list"],
    ]


def _client_row(client: ClientOut) -> Element:
    return tr(".client-row")[
        # Same renderer as the sources table: the resolved name shows, the
        # address stays reachable as the title (FR-009's naming exception).
        td(".client-address")[source_name(client.address, client.hostname)],
        td(".client-ntp-hits")[str(client.ntp_hits)],
        td(".client-ntp-drops")[str(client.ntp_drops)],
        td(".client-interval")[client.poll_display],
        td(".client-last-seen")[client.last_seen_display],
        td(".client-nts-ke")[client.nts_ke_display],
    ]
