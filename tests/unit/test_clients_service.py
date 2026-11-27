"""Every rung of the dashboard's client-data availability ladder.

systemctl and the filesystem are mocked; no test here needs systemd, a reader,
or a chronyd.
"""

import subprocess
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from second_hand.clients_model import ReaderSnapshot, UnavailableReason
from second_hand.config import Settings
from second_hand.reader.publish import publish_snapshot
from second_hand.services.clients import (
    READER_NOT_INSTALLED,
    READER_NOT_RUNNING,
    SYSTEMCTL_ARGV,
    _unit_file_state,
    get_clients_state,
    is_local_chronyd,
)
from tests.unit.test_clients_model import make_snapshot


@pytest.fixture(autouse=True)
def fresh_unit_state_cache() -> Generator[None]:
    """The systemctl answer is TTL-cached; tests must not share it."""
    _unit_file_state.cache_clear()
    yield
    _unit_file_state.cache_clear()


def settings_with(tmp_path: Path, **overrides: object) -> Settings:
    fields: dict[str, object] = {
        "clients_snapshot_path": tmp_path / "snapshot.json",
        "chrony_address": "127.0.0.1:323",
    }
    fields.update(overrides)
    return Settings(**fields)  # type: ignore[arg-type]


def write_snapshot(tmp_path: Path, **overrides: object) -> ReaderSnapshot:
    snapshot = ReaderSnapshot.model_validate(make_snapshot(**overrides))
    publish_snapshot(snapshot, tmp_path / "snapshot.json")
    return snapshot


def systemctl_result(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=list(SYSTEMCTL_ARGV), returncode=0, stdout=stdout, stderr=""
    )


def patched_systemctl(unit_file_state: str):
    stdout = f"UnitFileState={unit_file_state}\nActiveState=inactive\n"
    return patch(
        "second_hand.services.clients.subprocess.run",
        return_value=systemctl_result(stdout),
    )


class TestIsLocalChronyd:
    @pytest.mark.parametrize(
        "address",
        [
            "/run/chrony/chronyd.sock",
            "127.0.0.1",
            "127.0.0.1:323",
            "::1",
            "[::1]:323",
            "localhost",
            "localhost:323",
        ],
    )
    def test_local(self, address: str) -> None:
        assert is_local_chronyd(address) is True

    @pytest.mark.parametrize(
        "address",
        [
            "192.168.1.5:323",
            "10.0.0.1",
            "time.example.com",
            "time.example.com:323",
            "2001:db8::1",
            "[2001:db8::1]:323",
        ],
    )
    def test_remote(self, address: str) -> None:
        assert is_local_chronyd(address) is False


class TestAbsentRungs:
    def test_flag_off(self, tmp_path: Path) -> None:
        """FR-016: off means absent, even with a fresh snapshot on disk."""
        write_snapshot(tmp_path)
        settings = settings_with(tmp_path, clients_enabled=False)
        assert get_clients_state(settings) is None

    def test_remote_chronyd(self, tmp_path: Path) -> None:
        """FR-020: a remote chronyd hides the panel with no notice."""
        write_snapshot(tmp_path)
        settings = settings_with(tmp_path, chrony_address="192.168.1.5:323")
        assert get_clients_state(settings) is None

    @pytest.mark.parametrize("unit_file_state", ["disabled", "masked"])
    def test_unit_disabled_or_masked(
        self, tmp_path: Path, unit_file_state: str
    ) -> None:
        """FR-016 route b: a deliberately disabled reader is off, not broken."""
        with patched_systemctl(unit_file_state):
            assert get_clients_state(settings_with(tmp_path)) is None


class TestUnavailableRungs:
    def test_unit_unknown_means_not_installed(self, tmp_path: Path) -> None:
        """FR-019: source/container installs render unavailable, not an error."""
        with patched_systemctl(""):
            state = get_clients_state(settings_with(tmp_path))
        assert state is not None
        assert state.status == "unavailable"
        assert state.reason == READER_NOT_INSTALLED

    def test_no_systemctl_means_not_installed(self, tmp_path: Path) -> None:
        with patch(
            "second_hand.services.clients.subprocess.run",
            side_effect=FileNotFoundError("systemctl"),
        ):
            state = get_clients_state(settings_with(tmp_path))
        assert state is not None
        assert state.reason == READER_NOT_INSTALLED

    def test_enabled_but_no_snapshot_means_not_running(self, tmp_path: Path) -> None:
        """R3's distinction: enabled-but-stopped is a failure, not "off"."""
        with patched_systemctl("enabled"):
            state = get_clients_state(settings_with(tmp_path))
        assert state is not None
        assert state.status == "unavailable"
        assert state.reason == READER_NOT_RUNNING

    def test_malformed_snapshot_treated_like_missing(self, tmp_path: Path) -> None:
        (tmp_path / "snapshot.json").write_text("{definitely not json")
        with patched_systemctl("enabled"):
            state = get_clients_state(settings_with(tmp_path))
        assert state is not None
        assert state.reason == READER_NOT_RUNNING

    def test_wrong_schema_version_treated_like_missing(self, tmp_path: Path) -> None:
        (tmp_path / "snapshot.json").write_text('{"schema_version": 2}')
        with patched_systemctl("enabled"):
            state = get_clients_state(settings_with(tmp_path))
        assert state is not None
        assert state.status == "unavailable"


class TestSnapshotRungs:
    def test_fresh_snapshot_renders(self, tmp_path: Path) -> None:
        snapshot = write_snapshot(tmp_path, taken_at=1000)
        state = get_clients_state(settings_with(tmp_path), now=1010)
        assert state is not None
        assert state.status == "ok"
        assert state.snapshot == snapshot
        assert state.age_seconds == 10
        assert state.stale is False

    def test_stale_snapshot_marked(self, tmp_path: Path) -> None:
        """FR-018: stale past three missed intervals, age always computed."""
        write_snapshot(tmp_path, taken_at=1000, interval=30)
        state = get_clients_state(settings_with(tmp_path), now=1091)
        assert state is not None
        assert state.stale is True
        assert state.age_seconds == 91

    def test_boundary_age_is_not_stale(self, tmp_path: Path) -> None:
        write_snapshot(tmp_path, taken_at=1000, interval=30)
        state = get_clients_state(settings_with(tmp_path), now=1090)
        assert state is not None
        assert state.stale is False

    def test_reader_reported_reason_passes_through(self, tmp_path: Path) -> None:
        """FR-017: the reader's own unavailable reasons reach the panel."""
        write_snapshot(
            tmp_path,
            status="unavailable",
            reason="chrony_too_old",
            reason_detail="chrony 3.x",
            summary=None,
            totals=None,
            clients=[],
        )
        state = get_clients_state(settings_with(tmp_path), now=1795900000)
        assert state is not None
        assert state.status == "unavailable"
        assert state.reason == UnavailableReason.CHRONY_TOO_OLD.value
        assert state.reason_detail == "chrony 3.x"

    def test_fresh_snapshot_needs_no_systemctl(self, tmp_path: Path) -> None:
        """Dev installs without systemd render data (quickstart dev loop)."""
        write_snapshot(tmp_path)
        with patch("second_hand.services.clients.subprocess.run") as run:
            state = get_clients_state(settings_with(tmp_path), now=1795900000)
        assert state is not None
        assert state.status == "ok"
        run.assert_not_called()
