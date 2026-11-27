"""Atomic publishing and the reader's process behaviour."""

import json
import threading
from pathlib import Path
from unittest.mock import patch

from second_hand.clients_model import ReaderSnapshot, UnavailableReason
from second_hand.config import Settings
from second_hand.reader import main
from second_hand.reader.publish import publish_snapshot


def make_snapshot(taken_at: int = 1795900000) -> ReaderSnapshot:
    return ReaderSnapshot(
        schema_version=1,
        taken_at=taken_at,
        interval=30,
        status="unavailable",
        reason=UnavailableReason.CHRONYD_UNREACHABLE,
        reason_detail="506 Cannot talk to daemon",
    )


class TestPublishSnapshot:
    def test_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "snapshot.json"
        snapshot = make_snapshot()
        publish_snapshot(snapshot, path)
        assert ReaderSnapshot.model_validate_json(path.read_bytes()) == snapshot

    def test_no_temp_file_left(self, tmp_path: Path) -> None:
        path = tmp_path / "snapshot.json"
        publish_snapshot(make_snapshot(), path)
        assert [p.name for p in tmp_path.iterdir()] == ["snapshot.json"]

    def test_readers_always_see_whole_documents(self, tmp_path: Path) -> None:
        """Concurrent rewrites never expose a partial file (FR-012 channel)."""
        path = tmp_path / "snapshot.json"
        publish_snapshot(make_snapshot(0), path)
        stop = threading.Event()

        def rewrite() -> None:
            taken_at = 1
            while not stop.is_set():
                publish_snapshot(make_snapshot(taken_at), path)
                taken_at += 1

        writer = threading.Thread(target=rewrite)
        writer.start()
        try:
            for _ in range(500):
                # json.loads raises on a torn read; every read must be whole.
                document = json.loads(path.read_bytes())
                assert document["schema_version"] == 1
        finally:
            stop.set()
            writer.join()


class TestReaderProcess:
    def test_disabled_flag_exits_zero_before_any_chronyc_call(self) -> None:
        """FR-016 route a: the unit must sit inactive, not restart-loop."""
        settings = Settings(clients_enabled=False)
        with (
            patch("second_hand.reader.collect_snapshot") as collect,
            patch("second_hand.reader.publish_snapshot") as publish,
        ):
            assert main(settings) == 0
        collect.assert_not_called()
        publish.assert_not_called()

    def test_one_cycle_collects_and_publishes(self, tmp_path: Path) -> None:
        settings = Settings(
            clients_snapshot_path=tmp_path / "snapshot.json", reader_interval=30
        )
        with (
            patch(
                "second_hand.reader.collect_snapshot", return_value=make_snapshot()
            ) as collect,
            patch("second_hand.reader.publish_snapshot") as publish,
            patch("second_hand.reader.time.sleep", side_effect=KeyboardInterrupt),
        ):
            assert main(settings) == 0
        collect.assert_called_once_with(interval=30, max_rows=100)
        publish.assert_called_once_with(make_snapshot(), settings.clients_snapshot_path)
