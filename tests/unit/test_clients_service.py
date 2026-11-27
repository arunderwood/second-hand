"""Every rung of the dashboard's client-data availability ladder.

The reader unit's on-disk state and the filesystem are faked; no test here
needs systemd, a reader, or a chronyd.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from second_hand.clients_model import ReaderSnapshot, UnavailableReason
from second_hand.config import Settings
from second_hand.reader.publish import publish_snapshot
from second_hand.services import clients as clients_service
from second_hand.services.clients import (
    READER_NOT_INSTALLED,
    READER_NOT_RUNNING,
    _reader_unit_state,
    get_clients_state,
    is_local_chronyd,
)
from tests.unit.test_clients_model import make_snapshot


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


def patched_unit_state(state: str):
    return patch.object(clients_service, "_reader_unit_state", return_value=state)


@pytest.fixture
def unit_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Point the on-disk unit-state constants at a scratch layout."""
    lib = tmp_path / "usr-lib" / "second-hand-reader.service"
    etc_unit = tmp_path / "etc" / "second-hand-reader.service"
    run_unit = tmp_path / "run" / "second-hand-reader.service"
    wants = tmp_path / "wants" / "second-hand-reader.service"
    for path in (lib, etc_unit, run_unit, wants):
        path.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(clients_service, "_UNIT_FILE_PATHS", (lib, etc_unit))
    monkeypatch.setattr(clients_service, "_MASK_PATHS", (etc_unit, run_unit))
    monkeypatch.setattr(clients_service, "_ENABLED_LINK", wants)
    return {"lib": lib, "etc": etc_unit, "run": run_unit, "wants": wants}


class TestReaderUnitState:
    """The on-disk layout is the whole contract: no subprocess, no D-Bus."""

    def test_nothing_on_disk_is_not_installed(
        self, unit_paths: dict[str, Path]
    ) -> None:
        assert _reader_unit_state() == "not-installed"

    def test_unit_file_without_wants_link_is_disabled(
        self, unit_paths: dict[str, Path]
    ) -> None:
        unit_paths["lib"].write_text("[Unit]\n")
        assert _reader_unit_state() == "disabled"

    def test_wants_link_is_enabled(self, unit_paths: dict[str, Path]) -> None:
        unit_paths["lib"].write_text("[Unit]\n")
        unit_paths["wants"].symlink_to(unit_paths["lib"])
        assert _reader_unit_state() == "enabled"

    def test_dangling_wants_link_still_reads_enabled(
        self, unit_paths: dict[str, Path]
    ) -> None:
        unit_paths["wants"].symlink_to(unit_paths["lib"])
        assert _reader_unit_state() == "enabled"

    @pytest.mark.parametrize("where", ["etc", "run"])
    def test_devnull_symlink_is_masked(
        self, unit_paths: dict[str, Path], where: str
    ) -> None:
        """Masking wins even while the enablement symlink lingers."""
        unit_paths["lib"].write_text("[Unit]\n")
        unit_paths["wants"].symlink_to(unit_paths["lib"])
        unit_paths[where].symlink_to("/dev/null")
        assert _reader_unit_state() == "masked"

    def test_admin_unit_in_etc_is_installed(self, unit_paths: dict[str, Path]) -> None:
        unit_paths["etc"].write_text("[Unit]\n")
        assert _reader_unit_state() == "disabled"


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

    @pytest.mark.parametrize("unit_state", ["disabled", "masked"])
    def test_unit_disabled_or_masked(self, tmp_path: Path, unit_state: str) -> None:
        """FR-016 route b: a deliberately disabled reader is off, not broken."""
        with patched_unit_state(unit_state):
            assert get_clients_state(settings_with(tmp_path)) is None


class TestUnavailableRungs:
    def test_no_unit_means_not_installed(self, tmp_path: Path) -> None:
        """FR-019: source/container installs render unavailable, not an error."""
        with patched_unit_state("not-installed"):
            state = get_clients_state(settings_with(tmp_path))
        assert state is not None
        assert state.status == "unavailable"
        assert state.reason == READER_NOT_INSTALLED

    def test_enabled_but_no_snapshot_means_not_running(self, tmp_path: Path) -> None:
        """R3's distinction: enabled-but-stopped is a failure, not "off"."""
        with patched_unit_state("enabled"):
            state = get_clients_state(settings_with(tmp_path))
        assert state is not None
        assert state.status == "unavailable"
        assert state.reason == READER_NOT_RUNNING

    def test_malformed_snapshot_treated_like_missing(self, tmp_path: Path) -> None:
        (tmp_path / "snapshot.json").write_text("{definitely not json")
        with patched_unit_state("enabled"):
            state = get_clients_state(settings_with(tmp_path))
        assert state is not None
        assert state.reason == READER_NOT_RUNNING

    def test_wrong_schema_version_treated_like_missing(self, tmp_path: Path) -> None:
        (tmp_path / "snapshot.json").write_text('{"schema_version": 2}')
        with patched_unit_state("enabled"):
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

    def test_fresh_snapshot_needs_no_unit_check(self, tmp_path: Path) -> None:
        """Dev installs without systemd render data (quickstart dev loop)."""
        write_snapshot(tmp_path)
        with patch.object(clients_service, "_reader_unit_state") as unit_state:
            state = get_clients_state(settings_with(tmp_path), now=1795900000)
        assert state is not None
        assert state.status == "ok"
        unit_state.assert_not_called()
