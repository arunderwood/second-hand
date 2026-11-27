"""Atomically publish a ReaderSnapshot to the snapshot file.

Write-to-temp, fsync, rename: a reader always sees a complete document or the
previous one, never a partial write (contracts/reader-snapshot.md).
"""

import os
from pathlib import Path

from second_hand.clients_model import ReaderSnapshot

__all__ = ["publish_snapshot"]


def publish_snapshot(snapshot: ReaderSnapshot, path: Path) -> None:
    """Replace ``path`` with ``snapshot`` as one atomic rename."""
    # The temp file must live in the target directory: rename() is only atomic
    # within a filesystem.
    tmp = path.with_name(path.name + ".tmp")
    data = snapshot.model_dump_json()
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)
