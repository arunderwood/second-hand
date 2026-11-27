"""The reader's chronyc invocation, CSV parsing, and aggregation.

The CSV fixtures are verbatim captures from chronyd on the four target
distributions (chrony 4.3, 4.5, 4.6.1, 4.8), so a format drift in a future
chrony shows up here as a fixture update, not a production surprise.
"""

import subprocess
from unittest.mock import patch

import pytest

from second_hand.clients_model import (
    LastSeenBucket,
    PollIntervalBucket,
    UnavailableReason,
)
from second_hand.reader.collect import (
    CLIENTS_ARGV,
    SERVERSTATS_ARGV,
    collect_snapshot,
)

# chronyc -c -n clients -k: identical shape on chrony 4.3/4.5/4.6.1/4.8.
# 127 is the int8 "none" sentinel for intervals; 4294967295 the uint32 "never"
# for ages. The ::1 row is monitoring-only (0 NTP hits, 0 NTS-KE hits).
CLIENTS_CSV = (
    "127.0.0.1,5,0,-2,127,1,0,0,127,4294967295\n"
    "::1,0,0,127,127,4294967295,0,0,127,4294967295\n"
)

# chronyc -c serverstats: chrony 4.3 emits 11 fields.
SERVERSTATS_CSV_43 = "5,0,4,0,0,0,0,0,0,0,0\n"
# chrony 4.5, 4.6.1 and 4.8 append timestamp counters: 17 fields.
SERVERSTATS_CSV_45_PLUS = "5,0,4,0,0,0,0,0,0,0,0,0,5,5,0,0,0\n"


def completed(
    argv: tuple[str, ...], stdout: str, returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=list(argv), returncode=returncode, stdout=stdout, stderr=""
    )


def run_collect(
    clients_csv: str,
    serverstats_csv: str = SERVERSTATS_CSV_45_PLUS,
    *,
    max_rows: int = 100,
):
    """collect_snapshot with chronyc mocked to the given outputs."""

    def fake_run(argv: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        if tuple(argv) == CLIENTS_ARGV:  # type: ignore[arg-type]
            return completed(CLIENTS_ARGV, clients_csv)
        assert tuple(argv) == SERVERSTATS_ARGV  # type: ignore[arg-type]
        return completed(SERVERSTATS_ARGV, serverstats_csv)

    with patch("second_hand.reader.collect.subprocess.run", side_effect=fake_run):
        return collect_snapshot(interval=30, max_rows=max_rows)


class TestCapturedFixtures:
    @pytest.mark.parametrize(
        "serverstats_csv",
        [SERVERSTATS_CSV_43, SERVERSTATS_CSV_45_PLUS],
        ids=["chrony-4.3", "chrony-4.5-4.8"],
    )
    def test_real_capture_parses(self, serverstats_csv: str) -> None:
        snapshot = run_collect(CLIENTS_CSV, serverstats_csv)
        assert snapshot.status == "ok"
        assert snapshot.schema_version == 1
        assert snapshot.summary is not None
        assert snapshot.totals is not None
        assert snapshot.totals.ntp_received == 5
        assert snapshot.totals.cmd_received == 4
        assert snapshot.totals.log_records_dropped == 0

    def test_monitoring_only_host_excluded(self) -> None:
        """::1 sent only commands, so it is not a client anywhere (FR-001)."""
        snapshot = run_collect(CLIENTS_CSV)
        assert snapshot.summary is not None
        assert snapshot.summary.total_clients == 1
        assert [c.address for c in snapshot.clients] == ["127.0.0.1"]
        assert snapshot.clients_truncated == 0

    def test_sentinels_mapped(self) -> None:
        """127 means no interval; uint32 max means never seen."""
        snapshot = run_collect(CLIENTS_CSV)
        record = snapshot.clients[0]
        assert record.ntp_interval == -2
        assert record.ntp_interval_limited is None
        assert record.last_ntp_seconds == 1
        assert record.last_nts_ke_seconds is None
        assert record.last_seen_seconds == 1
        assert record.is_nts is False


class TestAggregation:
    def test_nts_split_and_buckets(self) -> None:
        clients_csv = (
            # NTP-only, fast poll, seen 30s ago.
            "192.0.2.1,100,0,6,127,30,0,0,127,4294967295\n"
            # NTS client, slower poll, seen 2h ago via NTS-KE.
            "192.0.2.2,50,0,7,127,7200,3,0,127,7200\n"
            # Rate-limited client, poll unknown, seen 2 days ago.
            "192.0.2.3,10,4,127,8,172800,0,0,127,4294967295\n"
        )
        snapshot = run_collect(clients_csv)
        summary = snapshot.summary
        assert summary is not None
        assert summary.total_clients == 3
        assert summary.nts_clients == 1
        assert summary.ntp_clients == 2
        assert summary.rate_limited_clients == 1
        assert summary.total_dropped_requests == 4
        assert summary.last_seen_buckets == {
            LastSeenBucket.LAST_MINUTE: 1,
            LastSeenBucket.LAST_HOUR: 0,
            LastSeenBucket.LAST_DAY: 1,
            LastSeenBucket.OLDER: 1,
        }
        assert summary.poll_interval_buckets == {
            PollIntervalBucket.FAST: 1,
            PollIntervalBucket.NORMAL: 1,
            PollIntervalBucket.SLOW: 0,
            PollIntervalBucket.UNKNOWN: 1,
        }

    def test_truncation_keeps_most_recent(self) -> None:
        """The cap keeps the most recently seen and counts the rest (FR-006)."""
        clients_csv = "".join(
            f"192.0.2.{i},10,0,6,127,{i * 100},0,0,127,4294967295\n"
            for i in range(1, 11)
        )
        snapshot = run_collect(clients_csv, max_rows=3)
        assert snapshot.summary is not None
        assert snapshot.summary.total_clients == 10
        assert snapshot.clients_truncated == 7
        assert [c.address for c in snapshot.clients] == [
            "192.0.2.1",
            "192.0.2.2",
            "192.0.2.3",
        ]
        assert [c.last_seen_seconds for c in snapshot.clients] == [100, 200, 300]

    def test_zero_clients_is_ok_not_unavailable(self) -> None:
        """An empty log with logging on is a real zero, not a failure."""
        snapshot = run_collect("")
        assert snapshot.status == "ok"
        assert snapshot.summary is not None
        assert snapshot.summary.total_clients == 0


class TestPoisoning:
    """Any malformed row invalidates the whole snapshot — no partial numbers."""

    @pytest.mark.parametrize(
        "bad_row",
        [
            "not-an-address,10,0,6,127,30,0,0,127,4294967295",
            "192.0.2.1,ten,0,6,127,30,0,0,127,4294967295",
            "192.0.2.1,10,0,6,127",
            "192.0.2.1,-3,0,6,127,30,0,0,127,4294967295",
        ],
        ids=["bad-address", "non-numeric", "short-row", "negative-count"],
    )
    def test_bad_row_poisons_snapshot(self, bad_row: str) -> None:
        good = "192.0.2.9,10,0,6,127,30,0,0,127,4294967295"
        snapshot = run_collect(f"{good}\n{bad_row}\n")
        assert snapshot.status == "unavailable"
        assert snapshot.reason == UnavailableReason.PARSE_ERROR
        assert snapshot.clients == []
        assert snapshot.summary is None

    def test_short_serverstats_poisons_snapshot(self) -> None:
        snapshot = run_collect(CLIENTS_CSV, "5,0,4\n")
        assert snapshot.status == "unavailable"
        assert snapshot.reason == UnavailableReason.PARSE_ERROR


class TestFailureMapping:
    """chronyc's numbered failures, captured verbatim on all four distros."""

    @pytest.mark.parametrize(
        ("output", "reason"),
        [
            ("501 Not authorised\n", UnavailableReason.PERMISSION_DENIED),
            ("506 Cannot talk to daemon\n", UnavailableReason.CHRONYD_UNREACHABLE),
            (
                # What a stopped chronyd looks like from inside the hardened
                # unit, where no UDP fallback is possible (deb harness capture).
                "Could not open connection to daemon\n",
                UnavailableReason.CHRONYD_UNREACHABLE,
            ),
            (
                "519 Client logging is not active in the daemon\n",
                UnavailableReason.CLIENT_LOGGING_DISABLED,
            ),
            (
                "chronyc: invalid option -- 'k'\nUsage: chronyc [OPTION]...\n",
                UnavailableReason.CHRONY_TOO_OLD,
            ),
            ("something novel\n", UnavailableReason.PARSE_ERROR),
        ],
        ids=["501", "506", "no-socket", "519", "old-chronyc", "unknown"],
    )
    def test_nonzero_exit_classified(
        self, output: str, reason: UnavailableReason
    ) -> None:
        with patch(
            "second_hand.reader.collect.subprocess.run",
            return_value=completed(CLIENTS_ARGV, output, returncode=1),
        ):
            snapshot = collect_snapshot(interval=30, max_rows=100)
        assert snapshot.status == "unavailable"
        assert snapshot.reason == reason
        assert snapshot.reason_detail

    def test_missing_chronyc_is_unreachable(self) -> None:
        with patch(
            "second_hand.reader.collect.subprocess.run",
            side_effect=FileNotFoundError("chronyc"),
        ):
            snapshot = collect_snapshot(interval=30, max_rows=100)
        assert snapshot.reason == UnavailableReason.CHRONYD_UNREACHABLE

    def test_timeout_is_unreachable(self) -> None:
        with patch(
            "second_hand.reader.collect.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=list(CLIENTS_ARGV), timeout=10),
        ):
            snapshot = collect_snapshot(interval=30, max_rows=100)
        assert snapshot.reason == UnavailableReason.CHRONYD_UNREACHABLE


class TestArgvInvariants:
    def test_argvs_are_read_only(self) -> None:
        """Only the two fixed monitoring queries, never -r (FR-011)."""
        assert CLIENTS_ARGV == ("chronyc", "-c", "-n", "clients", "-k")
        assert SERVERSTATS_ARGV == ("chronyc", "-c", "serverstats")
        assert "-r" not in CLIENTS_ARGV
        assert "-r" not in SERVERSTATS_ARGV
