"""Display rules for chrony sources, shared by the HTML tables and the JSON API.

The dashboard renders the sources table server-side and then patches it from
``/api/sources``, so both must agree on every label and CSS class. Keeping the
rules here means the browser applies values the server computed rather than
re-deriving them.
"""

from typing import NamedTuple

from pychrony import Source, SourceStats

from second_hand.utils import format_reachability_visual

__all__ = [
    "SOURCE_STATE_CLASSES",
    "ModeDisplay",
    "mode_display",
    "reachability_percent",
    "source_state_class",
    "state_label",
    "stats_address_label",
]


class ModeDisplay(NamedTuple):
    """How a chrony source mode is presented.

    Attributes:
        short: Badge text.
        full: Badge tooltip.
        css_class: Badge modifier, also the API's ``mode`` value.
    """

    short: str
    full: str
    css_class: str


_MODE_DISPLAY: dict[str, ModeDisplay] = {
    "CLIENT": ModeDisplay("Srv", "Server", "server"),
    "PEER": ModeDisplay("Peer", "Peer", "peer"),
    "REFCLOCK": ModeDisplay("Ref", "Reference Clock", "refclock"),
}
_UNKNOWN_MODE = ModeDisplay("?", "Unknown", "server")

# Every class source_state_class can return, so a client can clear the old one.
SOURCE_STATE_CLASSES = (
    "source-selected",
    "source-falseticker",
    "source-jittery",
    "source-unreachable",
)


def mode_display(mode_name: str) -> ModeDisplay:
    """Look up the presentation for a pychrony ``SourceMode`` name."""
    return _MODE_DISPLAY.get(mode_name, _UNKNOWN_MODE)


def state_label(state_name: str) -> str:
    """Turn a pychrony ``SourceState`` name into a label, e.g. ``Not Selected``."""
    return state_name.replace("_", " ").title()


def source_state_class(source: Source) -> str | None:
    """Pick the row highlight for a source, or None for an unremarkable one."""
    match source.state.name:
        case "SELECTED":
            return "source-selected"
        case "FALSETICKER":
            return "source-falseticker"
        case "JITTERY":
            return "source-jittery"
    if not source.is_reachable():
        return "source-unreachable"
    return None


def stats_address_label(stats: SourceStats) -> str:
    """Name a source-statistics row.

    chronyd reports an address only for network sources; a reference clock
    carries its four-character name in the reference ID instead, which is what
    chrony itself and the NTP sources table show (``NMEA``, ``PPS``). Fall back
    to the hex reference ID when those bytes are not printable text.
    """
    if stats.address:
        return stats.address
    raw = stats.reference_id.to_bytes(4, "big")
    if all(byte == 0 or 32 <= byte < 127 for byte in raw):
        name = raw.rstrip(b"\x00").decode("ascii").strip()
        if name:
            return name
    return f"{stats.reference_id:08X}"


def reachability_percent(reachability: int) -> int:
    """Share of the last eight polls that got a reply, as a whole percentage."""
    return int(sum(format_reachability_visual(reachability)) / 8 * 100)
