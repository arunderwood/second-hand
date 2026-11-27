"""Client-visibility integration tests against a real chronyd (SC-003).

Runs inside the docker test container, where chronyd serves NTP on loopback
and this process is privileged enough to use chronyc. Proves the reader's
queries change nothing: repeated collection leaves chronyd's client and NTP
counters exactly as they were (FR-011).

Counters that the measurement itself moves are treated for what they are:
every chronyc invocation is a received command packet, so serverstats'
command counters can only be checked for monotonic growth, never for
byte-identity — and the clients report's "seconds since last" columns tick
with wall time, so comparisons exclude them. Everything else must be
byte-identical.
"""

import socket
import subprocess
import time

import pytest

from second_hand.reader.collect import (
    CLIENTS_ARGV,
    SERVERSTATS_ARGV,
    collect_snapshot,
)

pytestmark = pytest.mark.integration

NTP_PROBES = 5

# clients -k CSV positions whose values tick with wall time (seconds since
# last NTP / last NTS-KE); every other position must not move.
_TIME_COLUMNS = {5, 9}
# serverstats CSV positions the measurement itself increments (command
# packets received/dropped); every other position must not move.
_CMD_COLUMNS = {2, 3}


def run_chronyc(argv: tuple[str, ...]) -> str:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def send_ntp_probe() -> None:
    """One NTP mode-3 client request to the local chronyd."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(5)
        s.sendto(bytes([0x23]) + bytes(47), ("127.0.0.1", 123))
        reply, _ = s.recvfrom(1024)
    assert len(reply) == 48


def stable_client_fields(output: str) -> list[tuple[str, ...]]:
    rows = [line.split(",") for line in output.splitlines() if line.strip()]
    return sorted(
        tuple(field for i, field in enumerate(row) if i not in _TIME_COLUMNS)
        for row in rows
    )


def stable_serverstats_fields(output: str) -> list[str]:
    fields = output.strip().split(",")
    return [field for i, field in enumerate(fields) if i not in _CMD_COLUMNS]


def cmd_received(output: str) -> int:
    return int(output.strip().split(",")[2])


@pytest.fixture(scope="module")
def client_traffic(check_chronyd_running: bool) -> None:
    """Real NTP traffic plus a monitoring-only access, both in the log."""
    for _ in range(NTP_PROBES):
        send_ntp_probe()
        time.sleep(0.2)
    # A UDP command from ::1 creates a client-log entry with only command
    # hits: the kind of host FR-001 says must never count as a client.
    subprocess.run(
        ("chronyc", "-h", "::1", "tracking"),
        capture_output=True,
        text=True,
        timeout=10,
    )


class TestCounterInvariance:
    """SC-003: ten consecutive collections change no counter."""

    def test_ten_collections_leave_counters_unchanged(
        self, client_traffic: None
    ) -> None:
        clients_before = run_chronyc(CLIENTS_ARGV)
        serverstats_before = run_chronyc(SERVERSTATS_ARGV)

        for _ in range(10):
            snapshot = collect_snapshot(interval=30, max_rows=100)
            assert snapshot.status == "ok", snapshot.reason_detail

        clients_after = run_chronyc(CLIENTS_ARGV)
        serverstats_after = run_chronyc(SERVERSTATS_ARGV)

        assert stable_client_fields(clients_before) == stable_client_fields(
            clients_after
        )
        assert stable_serverstats_fields(
            serverstats_before
        ) == stable_serverstats_fields(serverstats_after)
        # Command counters may only grow (our own queries), never reset.
        assert cmd_received(serverstats_after) >= cmd_received(serverstats_before)


class TestSnapshotContent:
    def test_snapshot_reflects_the_traffic(self, client_traffic: None) -> None:
        snapshot = collect_snapshot(interval=30, max_rows=100)
        assert snapshot.status == "ok"
        assert snapshot.summary is not None and snapshot.totals is not None

        addresses = [record.address for record in snapshot.clients]
        assert "127.0.0.1" in addresses
        probe = next(r for r in snapshot.clients if r.address == "127.0.0.1")
        assert probe.ntp_hits >= NTP_PROBES
        assert snapshot.summary.total_clients >= 1
        assert snapshot.totals.ntp_received >= NTP_PROBES

    def test_monitoring_only_host_is_absent(self, client_traffic: None) -> None:
        """The ::1 command access exists in chronyd's log but is no client."""
        raw_rows = run_chronyc(("chronyc", "-c", "-n", "clients")).splitlines()
        assert any(row.startswith("::1,") for row in raw_rows), (
            "the monitoring access never reached the client log; "
            "the exclusion assertion would be vacuous"
        )
        snapshot = collect_snapshot(interval=30, max_rows=100)
        addresses = [record.address for record in snapshot.clients]
        assert "::1" not in addresses
