"""Dashboard-side client data: snapshot loading and the availability ladder.

The reader publishes; this module decides what the dashboard shows. A snapshot
is untrusted input even though it is a local file: anything missing, stale,
malformed, or version-skewed degrades to a rendered state, never a 500.
"""

import ipaddress
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cachetools.func import ttl_cache
from pydantic import ValidationError

from second_hand.clients_model import ReaderSnapshot
from second_hand.config import Settings, get_settings

logger = logging.getLogger(__name__)

__all__ = [
    "READER_UNIT",
    "SYSTEMCTL_ARGV",
    "ClientsState",
    "get_clients_state",
    "is_local_chronyd",
]

READER_UNIT = "second-hand-reader.service"

# Fixed argv, read-only unit-property query over D-Bus. Nothing user-controlled
# is ever passed to subprocess.
SYSTEMCTL_ARGV = (
    "systemctl",
    "show",
    READER_UNIT,
    "--property=UnitFileState,ActiveState",
)

_SYSTEMCTL_TIMEOUT_SECONDS = 5

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
    4. No (or invalid) snapshot -> ask systemd why: a deliberately disabled or
       masked unit is "off" (absent, FR-016 route b); an unknown unit means a
       non-packaged install (unavailable, FR-019); anything else is a reader
       that should be publishing but is not (unavailable, FR-017).

    The snapshot outranks the unit query so that installs without systemd —
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

    unit_file_state = _unit_file_state()
    if unit_file_state in ("disabled", "masked", "masked-runtime"):
        return None
    if unit_file_state:
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


@ttl_cache(maxsize=1, ttl=5.0)
def _unit_file_state() -> str:
    """The reader unit's UnitFileState, '' when systemd cannot say.

    '' covers the unit being unknown and systemctl being absent, failing, or
    timing out — all the shapes a non-packaged install takes (FR-019). Cached
    briefly so a burst of dashboard requests costs one subprocess.
    """
    try:
        result = subprocess.run(
            SYSTEMCTL_ARGV,
            capture_output=True,
            text=True,
            timeout=_SYSTEMCTL_TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    for line in result.stdout.splitlines():
        key, _, value = line.partition("=")
        if key == "UnitFileState":
            return value.strip()
    return ""
