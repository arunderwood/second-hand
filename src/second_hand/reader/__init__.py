"""The second-hand-reader process: privileged, read-only chronyd client reader.

Runs as chrony's user, queries chronyd at a fixed interval, and publishes an
atomic JSON snapshot the unprivileged dashboard reads. Imports only the stdlib
and the shared models — never FastAPI or uvicorn.
"""

import logging
import time

from second_hand.config import Settings, get_settings
from second_hand.reader.collect import collect_snapshot
from second_hand.reader.publish import publish_snapshot

logger = logging.getLogger(__name__)

__all__ = ["main"]


def main(settings: Settings | None = None) -> int:
    """Run the reader loop until interrupted.

    Exits 0 immediately when the feature is off, so the unit sits inactive and
    ``Restart=on-failure`` does not bring it back (FR-016 route a).
    """
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    if settings is None:
        settings = get_settings()

    if not settings.clients_enabled:
        logger.info("client visibility disabled by configuration, exiting")
        return 0

    logger.info(
        "reader starting interval=%ds max_rows=%d snapshot=%s",
        settings.reader_interval,
        settings.clients_max_rows,
        settings.clients_snapshot_path,
    )
    try:
        while True:
            started = time.monotonic()
            snapshot = collect_snapshot(
                interval=settings.reader_interval,
                max_rows=settings.clients_max_rows,
            )
            publish_snapshot(snapshot, settings.clients_snapshot_path)
            logger.info(
                "published snapshot status=%s reason=%s clients=%d truncated=%d",
                snapshot.status,
                snapshot.reason.value if snapshot.reason else "-",
                len(snapshot.clients),
                snapshot.clients_truncated,
            )
            elapsed = time.monotonic() - started
            # The sleep anchors the fixed cadence (FR-013): one chronyd read
            # per interval, however long collection took, however many
            # dashboards are open.
            time.sleep(max(0.0, settings.reader_interval - elapsed))
    except KeyboardInterrupt:
        logger.info("reader stopping")
        return 0
