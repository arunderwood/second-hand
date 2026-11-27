"""Dashboard-side client data: snapshot loading and the availability ladder.

The reader publishes; this module decides what the dashboard shows. A snapshot
is untrusted input even though it is a local file: anything missing, stale,
malformed, or version-skewed degrades to a rendered state, never a 500.
"""

import ipaddress
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from second_hand.clients_model import ReaderSnapshot
from second_hand.config import Settings, get_settings

logger = logging.getLogger(__name__)

__all__ = [
    "READER_UNIT",
    "ClientsState",
    "get_clients_state",
    "is_local_chronyd",
]

READER_UNIT = "second-hand-reader.service"

# The reader unit's state is read from systemd's documented on-disk layout,
# never over D-Bus: dbus-daemon drops connections from DynamicUser services
# at the Hello stage, so no bus query can work from inside this service —
# and three stat() calls need no subprocess, no bus, and no sandbox
# allowances at all.
#
# Where the packaged (or admin-provided) unit file lives. Merged-/usr distros
# make /lib a symlink to /usr/lib, so both spellings resolve.
_UNIT_FILE_PATHS = (
    Path(f"/usr/lib/systemd/system/{READER_UNIT}"),
    Path(f"/lib/systemd/system/{READER_UNIT}"),
    Path(f"/etc/systemd/system/{READER_UNIT}"),
)
# Masking replaces the unit with a symlink to /dev/null, persistently in /etc
# or at runtime in /run.
_MASK_PATHS = (
    Path(f"/etc/systemd/system/{READER_UNIT}"),
    Path(f"/run/systemd/system/{READER_UNIT}"),
)
# Enablement is the [Install] symlink; the unit declares exactly one
# (WantedBy=multi-user.target), so this path is the whole answer.
_ENABLED_LINK = Path(f"/etc/systemd/system/multi-user.target.wants/{READER_UNIT}")

# Multiplier over the snapshot's own interval before its data is marked stale
# (FR-018): three missed cycles.
STALE_INTERVALS = 3

# The dashboard-side reasons; the reader's own are UnavailableReason values.
READER_NOT_INSTALLED = "reader_not_installed"
READER_NOT_RUNNING = "reader_not_running"

# A broken snapshot would otherwise log once per open tab per refresh; only a
# new error is a warning (same pattern as the RTC error in services.chrony).
_last_snapshot_error: str | None = None


@dataclass
class ClientsState:
    """What the Clients panel should show. Absence is represented by None
    from get_clients_state, never by an instance."""

    status: Literal["ok", "unavailable"]
    reason: str | None
    reason_detail: str | None
    snapshot: ReaderSnapshot | None
    age_seconds: int | None
    stale: bool


def get_clients_state(
    settings: Settings | None = None, *, now: float | None = None
) -> ClientsState | None:
    """Classify client-data availability; None means the panel is absent.

    The ladder, first match wins:

    1. Feature off (FR-016) -> absent.
    2. Configured chronyd is not on this machine (FR-020) -> absent: the
       reader only ever reads the local chronyd, so showing its data beside a
       remote server's stats would be misleading.
    3. A readable snapshot -> render it (fresh or stale; the snapshot itself
       may carry the reader's own unavailable reason, FR-017/FR-018).
    4. No (or invalid) snapshot -> read the unit's on-disk state: a
       deliberately disabled or masked unit is "off" (absent, FR-016 route b);
       a missing unit file means a non-packaged install (unavailable, FR-019);
       an enabled unit is a reader that should be publishing but is not
       (unavailable, FR-017).

    The snapshot outranks the unit check so that installs without systemd —
    the dev loop, containers — render data whenever the reader produces it.
    """
    if settings is None:
        settings = get_settings()
    if not settings.clients_enabled:
        return None
    if not is_local_chronyd(settings.chrony_address):
        return None

    snapshot = _load_snapshot(settings.clients_snapshot_path)
    if snapshot is not None:
        if now is None:
            now = time.time()
        age = max(0, int(now) - snapshot.taken_at)
        return ClientsState(
            status=snapshot.status,
            reason=snapshot.reason.value if snapshot.reason else None,
            reason_detail=snapshot.reason_detail,
            snapshot=snapshot,
            age_seconds=age,
            stale=age > STALE_INTERVALS * snapshot.interval,
        )

    unit_state = _reader_unit_state()
    if unit_state in ("disabled", "masked"):
        return None
    if unit_state == "enabled":
        reason, detail = (
            READER_NOT_RUNNING,
            "the reader service is enabled but has not published any data",
        )
    else:
        reason, detail = (
            READER_NOT_INSTALLED,
            "the client-data reader only ships with the Debian package",
        )
    return ClientsState(
        status="unavailable",
        reason=reason,
        reason_detail=detail,
        snapshot=None,
        age_seconds=None,
        stale=False,
    )


def is_local_chronyd(address: str) -> bool:
    """Whether the configured chronyd address is on this machine (FR-020).

    Local means a Unix socket path or a loopback address; any routable
    address is treated as remote even if it happens to be this host's own.
    """
    if address.startswith("/"):
        return True
    host = address
    if host.startswith("["):
        bracket_end = host.find("]")
        host = host[1:bracket_end] if bracket_end != -1 else host[1:]
    elif host.count(":") == 1:
        maybe_host, _, port = host.partition(":")
        if port.isdigit():
            host = maybe_host
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _load_snapshot(path: Path) -> ReaderSnapshot | None:
    """Read and validate the snapshot file; None for missing or invalid.

    An unknown schema_version fails validation here, which renders as the
    unavailable state rather than an error (contracts/reader-snapshot.md).
    """
    global _last_snapshot_error
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        _last_snapshot_error = None
        return None
    except OSError as e:
        _log_snapshot_error(f"snapshot unreadable at {path}: {e}")
        return None
    try:
        snapshot = ReaderSnapshot.model_validate_json(raw)
    except ValidationError as e:
        _log_snapshot_error(f"snapshot invalid at {path}: {e.error_count()} error(s)")
        return None
    _last_snapshot_error = None
    return snapshot


def _log_snapshot_error(error: str) -> None:
    global _last_snapshot_error
    if error != _last_snapshot_error:
        logger.warning("%s", error)
    _last_snapshot_error = error


def _reader_unit_state() -> Literal["masked", "enabled", "disabled", "not-installed"]:
    """The reader unit's state, from systemd's on-disk layout.

    "not-installed" covers every shape a non-packaged install takes — no unit
    file, no systemd at all (FR-019). A dangling enablement symlink still
    reads as enabled: the operator's intent is what decides off versus broken.
    """
    for path in _MASK_PATHS:
        try:
            if path.is_symlink() and os.readlink(path) == "/dev/null":
                return "masked"
        except OSError:
            continue
    try:
        if _ENABLED_LINK.is_symlink() or _ENABLED_LINK.exists():
            return "enabled"
    except OSError:
        pass
    for path in _UNIT_FILE_PATHS:
        try:
            if path.exists():
                return "disabled"
        except OSError:
            continue
    return "not-installed"
