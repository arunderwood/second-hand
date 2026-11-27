"""Collect one ReaderSnapshot from chronyd via the host's chronyc.

The distro's chronyc always matches the distro's chronyd, which is what makes
parsing its CSV output safe: chrony documents the wire protocol itself as
unstable across versions (research R1). Both argument vectors are module
constants and nothing user-controlled is ever passed to subprocess — the
constitution prohibits command injection paths outright.
"""

import heapq
import ipaddress
import logging
import subprocess
import time

from second_hand.clients_model import (
    SCHEMA_VERSION,
    ClientRecord,
    ClientSummary,
    LastSeenBucket,
    PollIntervalBucket,
    ReaderSnapshot,
    ServerTotals,
    UnavailableReason,
)

logger = logging.getLogger(__name__)

__all__ = ["CLIENTS_ARGV", "SERVERSTATS_ARGV", "collect_snapshot"]

# -n keeps chronyc from reverse-resolving client addresses: lookups on client
# IPs are forbidden (FR-009) and would stall on large logs. -k selects the
# NTS-KE columns instead of command counters, which both the NTS/NTP split and
# the monitoring-only exclusion need. Never -r: it resets counters.
CLIENTS_ARGV = ("chronyc", "-c", "-n", "clients", "-k")
SERVERSTATS_ARGV = ("chronyc", "-c", "serverstats")

SUBPROCESS_TIMEOUT_SECONDS = 10

# chronyc's CSV sentinels, identical across chrony 4.3-4.8: intervals are
# int8 with 127 meaning unknown/none; "seconds since last" is uint32 with the
# maximum meaning never.
_INTERVAL_NONE = 127
_LAST_NEVER = 2**32 - 1

# A clients row has exactly these fields on every supported version: address,
# NTP hits/drops/interval/interval-after-limit/last, NTS-KE hits/drops/
# interval/last.
_CLIENTS_FIELDS = 10
# The serverstats prefix we consume; later versions append more fields, which
# positional parsing ignores (research R6). chrony 4.3 emits 11.
_SERVERSTATS_FIELDS = 9

# Poll-interval bucket edges in log2 seconds: 2**6 = 64 s, 2**10 = 1024 s.
_POLL_FAST_MAX_LOG2 = 6
_POLL_NORMAL_MAX_LOG2 = 10

_LAST_SEEN_EDGES = (
    (60, LastSeenBucket.LAST_MINUTE),
    (3600, LastSeenBucket.LAST_HOUR),
    (86400, LastSeenBucket.LAST_DAY),
)


class CollectionError(Exception):
    """A chronyc invocation failed; carries the mapped unavailability."""

    def __init__(self, reason: UnavailableReason, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def collect_snapshot(*, interval: int, max_rows: int) -> ReaderSnapshot:
    """Query chronyd once and build the snapshot to publish.

    Operational failures become unavailable snapshots, never exceptions: the
    reader must keep cycling so the dashboard sees a fresh, honest state.
    """
    taken_at = int(time.time())
    try:
        clients_output = _run_chronyc(CLIENTS_ARGV)
        serverstats_output = _run_chronyc(SERVERSTATS_ARGV)
        summary, clients, truncated = _parse_clients(clients_output, max_rows)
        totals = _parse_serverstats(serverstats_output)
    except CollectionError as e:
        logger.warning("collection failed: %s (%s)", e.reason.value, e.detail)
        return ReaderSnapshot(
            schema_version=SCHEMA_VERSION,
            taken_at=taken_at,
            interval=interval,
            status="unavailable",
            reason=e.reason,
            reason_detail=e.detail,
        )
    return ReaderSnapshot(
        schema_version=SCHEMA_VERSION,
        taken_at=taken_at,
        interval=interval,
        status="ok",
        summary=summary,
        totals=totals,
        clients=clients,
        clients_truncated=truncated,
    )


def _run_chronyc(argv: tuple[str, ...]) -> str:
    """Run one fixed chronyc command, mapping failure to its reason.

    chronyd answers with a numbered status line on stdout, identical across
    chrony 4.3-4.8: 501 not authorised, 506 cannot talk to daemon, 519 client
    logging not active.
    """
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise CollectionError(
            UnavailableReason.CHRONYD_UNREACHABLE, "chronyc is not installed"
        ) from None
    except subprocess.TimeoutExpired:
        raise CollectionError(
            UnavailableReason.CHRONYD_UNREACHABLE,
            f"chronyc did not answer within {SUBPROCESS_TIMEOUT_SECONDS}s",
        ) from None
    if result.returncode != 0:
        raise _classify_failure(result.stdout + result.stderr)
    return result.stdout


def _classify_failure(output: str) -> CollectionError:
    """Map chronyc's failure output to the snapshot's reason enum."""
    line = output.strip().splitlines()[0].strip() if output.strip() else ""
    lowered = line.lower()
    if line.startswith("501") or "not authorised" in lowered:
        return CollectionError(UnavailableReason.PERMISSION_DENIED, line)
    # "506 Cannot talk to daemon" is the UDP-fallback answer; inside the
    # hardened unit (AF_UNIX only, IPAddressDeny=any) chronyc cannot even
    # fall back and says "Could not open connection to daemon" instead.
    if (
        line.startswith("506")
        or "cannot talk to daemon" in lowered
        or "could not open connection" in lowered
        or "connection refused" in lowered
    ):
        return CollectionError(UnavailableReason.CHRONYD_UNREACHABLE, line)
    if line.startswith("519") or "logging is not active" in lowered:
        return CollectionError(UnavailableReason.CLIENT_LOGGING_DISABLED, line)
    # An old chronyc rejects the clients options before ever reaching chronyd.
    if "invalid option" in lowered or "unrecognized" in lowered or "usage:" in lowered:
        return CollectionError(
            UnavailableReason.CHRONY_TOO_OLD,
            "the installed chrony does not support this query (4.0+ required)",
        )
    return CollectionError(
        UnavailableReason.PARSE_ERROR, line or "chronyc failed without output"
    )


def _parse_clients(
    output: str, max_rows: int
) -> tuple[ClientSummary, list[ClientRecord], int]:
    """Stream rows into aggregates plus a bounded most-recent top list.

    Memory stays O(max_rows) however large chronyd's log is (research R7):
    aggregation is incremental and only a recency heap of records is kept.
    Any malformed row poisons the whole snapshot (parse_error) — partial
    numbers must never be published (R6).
    """
    total = 0
    nts = 0
    rate_limited = 0
    dropped = 0
    last_seen_counts: dict[LastSeenBucket, int] = dict.fromkeys(LastSeenBucket, 0)
    poll_counts: dict[PollIntervalBucket, int] = dict.fromkeys(PollIntervalBucket, 0)
    # Min-heap on -last_seen keeps the worst (oldest) kept record at the root,
    # so a full heap evicts in O(log max_rows). seq breaks ties: ClientRecord
    # does not order.
    heap: list[tuple[int, int, ClientRecord]] = []

    for line_number, line in enumerate(output.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = _parse_client_row(line)
        except (ValueError, IndexError) as e:
            raise CollectionError(
                UnavailableReason.PARSE_ERROR,
                f"client log line {line_number} could not be parsed: {e}",
            ) from None
        if record is None:
            continue

        total += 1
        if record.is_nts:
            nts += 1
        if record.ntp_drops > 0:
            rate_limited += 1
        dropped += record.ntp_drops
        last_seen_counts[_last_seen_bucket(record.last_seen_seconds)] += 1
        poll_counts[_poll_bucket(record.ntp_interval)] += 1

        entry = (-record.last_seen_seconds, line_number, record)
        if len(heap) < max_rows:
            heapq.heappush(heap, entry)
        else:
            heapq.heappushpop(heap, entry)

    summary = ClientSummary(
        total_clients=total,
        nts_clients=nts,
        ntp_clients=total - nts,
        rate_limited_clients=rate_limited,
        total_dropped_requests=dropped,
        last_seen_buckets=last_seen_counts,
        poll_interval_buckets=poll_counts,
    )
    clients = [record for _, _, record in sorted(heap, reverse=True)]
    return summary, clients, total - len(clients)


def _parse_client_row(line: str) -> ClientRecord | None:
    """Parse one clients CSV row; None when it is monitoring-only.

    A host that only sent monitoring requests — the dashboard's own polling
    included — is not a client and appears in no count or table (FR-001).
    """
    fields = line.split(",")
    if len(fields) < _CLIENTS_FIELDS:
        raise ValueError(f"{len(fields)} fields, expected {_CLIENTS_FIELDS}")

    address = fields[0]
    ipaddress.ip_address(address)
    ntp_hits = _non_negative(fields[1])
    nts_ke_hits = _non_negative(fields[6])
    if ntp_hits == 0 and nts_ke_hits == 0:
        return None

    last_ntp = _last_seconds(fields[5])
    last_nts_ke = _last_seconds(fields[9])
    ages = [age for age in (last_ntp, last_nts_ke) if age is not None]

    return ClientRecord(
        address=address,
        ntp_hits=ntp_hits,
        ntp_drops=_non_negative(fields[2]),
        ntp_interval=_interval(fields[3]),
        ntp_interval_limited=_interval(fields[4]),
        last_ntp_seconds=last_ntp,
        nts_ke_hits=nts_ke_hits,
        nts_ke_drops=_non_negative(fields[7]),
        last_nts_ke_seconds=last_nts_ke,
        is_nts=nts_ke_hits > 0,
        last_seen_seconds=min(ages, default=0),
    )


def _parse_serverstats(output: str) -> ServerTotals:
    """Parse the one-line serverstats CSV by position (research R6)."""
    line = output.strip()
    fields = line.split(",") if line else []
    if len(fields) < _SERVERSTATS_FIELDS:
        raise CollectionError(
            UnavailableReason.PARSE_ERROR,
            f"serverstats has {len(fields)} fields, expected at least "
            f"{_SERVERSTATS_FIELDS}",
        )
    try:
        return ServerTotals(
            ntp_received=_non_negative(fields[0]),
            ntp_dropped=_non_negative(fields[1]),
            cmd_received=_non_negative(fields[2]),
            cmd_dropped=_non_negative(fields[3]),
            log_records_dropped=_non_negative(fields[4]),
            nts_ke_accepted=_non_negative(fields[5]),
            nts_ke_dropped=_non_negative(fields[6]),
            ntp_authenticated=_non_negative(fields[7]),
            ntp_interleaved=_non_negative(fields[8]),
        )
    except ValueError as e:
        raise CollectionError(
            UnavailableReason.PARSE_ERROR, f"serverstats could not be parsed: {e}"
        ) from None


def _non_negative(field: str) -> int:
    value = int(field)
    if value < 0:
        raise ValueError(f"negative counter {value}")
    return value


def _interval(field: str) -> int | None:
    """A log2-seconds interval; chronyc's int8 sentinel 127 means none."""
    value = int(field)
    return None if value == _INTERVAL_NONE else value


def _last_seconds(field: str) -> int | None:
    """Seconds since last request; chronyc's uint32 maximum means never."""
    value = int(field)
    if value < 0:
        raise ValueError(f"negative age {value}")
    return None if value >= _LAST_NEVER else value


def _last_seen_bucket(seconds: int) -> LastSeenBucket:
    for edge, bucket in _LAST_SEEN_EDGES:
        if seconds < edge:
            return bucket
    return LastSeenBucket.OLDER


def _poll_bucket(interval_log2: int | None) -> PollIntervalBucket:
    if interval_log2 is None:
        return PollIntervalBucket.UNKNOWN
    if interval_log2 <= _POLL_FAST_MAX_LOG2:
        return PollIntervalBucket.FAST
    if interval_log2 <= _POLL_NORMAL_MAX_LOG2:
        return PollIntervalBucket.NORMAL
    return PollIntervalBucket.SLOW
