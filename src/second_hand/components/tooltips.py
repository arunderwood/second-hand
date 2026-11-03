"""Tooltip content definitions for NTP/chrony fields.

Centralized storage for tooltip text used throughout the dashboard.
Descriptions follow the chronyc documentation and, where it is silent on a sign,
chronyc's source. Good and bad ranges are this dashboard's rules of thumb, not
chrony's. Those on health-colored values must match ``_HEALTH_THRESHOLDS``.
"""

from dataclasses import dataclass

__all__ = [
    "RTC_TOOLTIPS",
    "SOURCE_TOOLTIPS",
    "STATS_TOOLTIPS",
    "TRACKING_TOOLTIPS",
    "TooltipContent",
]


@dataclass(frozen=True)
class TooltipContent:
    """Container for tooltip text with optional threshold guidance."""

    description: str
    good_values: str | None = None
    bad_values: str | None = None


# Tracking Status Field Tooltips
TRACKING_TOOLTIPS: dict[str, TooltipContent] = {
    "sync_status": TooltipContent(
        description=(
            "Synchronized means chronyd has a time source to follow, at a stratum "
            "below 16. Not Sync means it has none right now, so the clock runs on "
            "its last known frequency."
        ),
    ),
    "reference": TooltipContent(
        description=(
            "Reference ID of the source chronyd follows. An IPv4 server shows its "
            "address and a reference clock its name, like GPS. An IPv6 server shows "
            "a hash, so check Ref IP. 127.127.1.1 means local mode, with no "
            "external source."
        ),
    ),
    "reference_ip": TooltipContent(
        description=(
            "Address of the source chronyd follows. A reference clock has none, so "
            "it shows an internal ID starting with ID#."
        ),
    ),
    "stratum": TooltipContent(
        description=(
            "Hops from a reference clock. A computer with one attached is stratum "
            "1, a machine syncing from it is stratum 2, and so on."
        ),
        good_values="1-3",
        bad_values="9+, and 16 means unsynchronized",
    ),
    "leap_status": TooltipContent(
        description=(
            "Whether a leap second is coming. Normal: none scheduled. Insert or "
            "Delete: a second will be added or dropped at an upcoming midnight UTC. "
            "Unsync: chronyd isn't synchronized."
        ),
        good_values="Normal",
        bad_values="Unsync",
    ),
    "ref_time": TooltipContent(
        description=(
            "When chronyd last processed a measurement from its source, in UTC. If "
            "this stops advancing, measurements have stopped arriving."
        ),
    ),
    # Current correction and last offset have opposite signs in chronyc: a positive
    # correction prints as "slow", a positive last offset means ahead.
    "offset": TooltipContent(
        description=(
            "Gap between the system clock and chronyd's estimate of true time. "
            "chronyd closes it by running the clock slightly fast or slow instead "
            "of jumping it. Positive means the system clock is behind, the opposite "
            "of Last Offset."
        ),
        good_values="under 10 ms",
        bad_values="over 100 ms",
    ),
    "last_offset": TooltipContent(
        description=(
            "Clock error chronyd estimated at its most recent update. Positive "
            "means the local clock was ahead of the time sources."
        ),
        good_values="under 10 ms",
        bad_values="over 100 ms",
    ),
    "rms_offset": TooltipContent(
        description=(
            "Long-term average of the offset at each clock update, as a root mean "
            "square, so it has no sign. A steadier read on accuracy than a single "
            "Last Offset."
        ),
        good_values="under 1 ms",
        bad_values="over 10 ms",
    ),
    "frequency": TooltipContent(
        description=(
            "How wrong the system clock's rate would be if chronyd stopped "
            "correcting it, in parts per million. 1 ppm is about 86 ms a day. "
            "Positive means fast, negative slow."
        ),
        good_values="under 10 ppm",
        bad_values="over 50 ppm",
    ),
    "residual_freq": TooltipContent(
        description=(
            "Gap between the frequency the source's measurements suggest and the "
            "one chronyd is using. It isn't always zero because chronyd smooths "
            "frequency changes."
        ),
        good_values="under 1 ppm",
    ),
    "skew": TooltipContent(
        description=(
            "Estimated error bound on Frequency: how far off chronyd thinks that "
            "figure could be."
        ),
        good_values="under 1 ppm",
        bad_values="over 5 ppm",
    ),
    "root_delay": TooltipContent(
        description=(
            "Total round-trip network delay to the stratum-1 computer at the top of "
            "the sync chain. Half of it counts toward the worst-case clock error."
        ),
        good_values="under 50 ms",
        bad_values="over 100 ms",
    ),
    "root_dispersion": TooltipContent(
        description=(
            "Uncertainty built up through every server back to stratum 1, from "
            "clock resolution, measurement noise and the like. If that stratum-1 "
            "computer is right, clock error is at most |Offset| + Root Disp + half "
            "of Root Delay."
        ),
        good_values="under 10 ms",
        bad_values="over 50 ms",
    ),
    "update_interval": TooltipContent(
        description=(
            "Time between the last two clock updates. chronyd updates the clock "
            "when the selected source has a new measurement, so this follows that "
            "source's polling rate."
        ),
    ),
}

# Source Field Tooltips
SOURCE_TOOLTIPS: dict[str, TooltipContent] = {
    "mode": TooltipContent(
        description=(
            "How chronyd gets time from this source. Srv (^ in chronyc): an NTP "
            "server it polls. Peer (=): an NTP peer, where either side can sync "
            "from the other. Ref (#): a reference clock on this machine."
        ),
    ),
    # chronyc maps RPY_SD_ST_UNSELECTED to "+" and RPY_SD_ST_SELECTABLE to "-", the
    # reverse of what the names suggest.
    "state": TooltipContent(
        description=(
            "Selected (*): the best source, steering the clock. Unselected (+): "
            "good, and combined with the best one. Selectable (-): good, but left "
            "out of that combination. Falseticker (x): disagrees with the other "
            "sources. Jittery (~): too variable. Nonselectable (?): unusable for "
            "now, for example unreachable."
        ),
    ),
    "address": TooltipContent(
        description=(
            "The source's reverse DNS name, otherwise its IP address, or its "
            "reference ID for a reference clock. Hover a name to see its address. "
            "Names aren't verified, so one is no proof of who runs the server."
        ),
    ),
    "stratum": TooltipContent(
        description=(
            "Stratum in this source's latest sample. A reference clock on this "
            "machine is 0, a server attached to one is 1, and each hop after that "
            "adds 1."
        ),
        good_values="0-3",
        bad_values="9+",
    ),
    "poll": TooltipContent(
        description=(
            "Countdown to the next expected poll, from the last sample and the "
            "current poll interval. chronyd sets that interval itself, between the "
            "source's minpoll and maxpoll: 64 s to about 17 min by default."
        ),
    ),
    # Compared as a number the register misleads: 200 (one reply in eight) is above
    # 177 (seven replies in eight), so the bad range names only 0.
    "reach": TooltipContent(
        description=(
            "Whether the last 8 polls got a reply. Each bar is one poll, newest on "
            "the right, and the number is the same 8 bits in octal. A new source "
            "climbs through 1, 3, 7, 17, 37, 77 and 177 as replies arrive."
        ),
        good_values="377 (all 8 replied)",
        bad_values="0 (no replies)",
    ),
    "last_rx": TooltipContent(
        description=(
            "How long ago the last good sample came from this source. Replies that "
            "fail chronyd's checks don't count."
        ),
    ),
    "latest_meas": TooltipContent(
        description=(
            "Offset in the last good sample, adjusted for clock changes chronyd has "
            "made since. Positive means the local clock is ahead of this source."
        ),
    ),
    "latest_meas_err": TooltipContent(
        description=(
            "Margin of error on Latest Meas, the +/- figure in chronyc sources. It "
            "adds half the root delay to the root dispersion on this source's path, "
            "so a distant server gets a wider margin."
        ),
    ),
    "orig_latest_meas": TooltipContent(
        description=(
            "Latest Meas as first measured, before adjusting for later changes to "
            "the local clock. Positive means the local clock was ahead."
        ),
    ),
}

# Source Statistics Field Tooltips
STATS_TOOLTIPS: dict[str, TooltipContent] = {
    "address": TooltipContent(
        description=(
            "The source these statistics belong to, named as in NTP Sources. Hover "
            "a row to highlight the same source in that table."
        ),
    ),
    "samples": TooltipContent(
        description=(
            "Measurements chronyd has kept for this source. It fits a straight line "
            "through them to estimate the source's offset and frequency."
        ),
    ),
    "runs": TooltipContent(
        description=(
            "Runs of same-sign residuals after that line fit, a residual being a "
            "sample's gap from the line. Random scatter gives about half of "
            "Samples. Too few means a straight line no longer fits, so chronyd "
            "drops older samples."
        ),
    ),
    "span": TooltipContent(
        description=(
            "Time between the oldest and newest samples. A longer span pins down "
            "frequency better. It shrinks when chronyd discards samples that no "
            "longer fit."
        ),
    ),
    "std_dev": TooltipContent(
        description=(
            "Estimated standard deviation of this source's samples, which shows how "
            "noisy its measurements are."
        ),
        good_values="under 50 µs",
        bad_values="over 1 ms",
    ),
    "resid_freq": TooltipContent(
        description=(
            "Frequency error still left in the local clock when measured against "
            "this source, in parts per million. Near zero means this source agrees "
            "with the frequency chronyd is using."
        ),
    ),
    "skew": TooltipContent(
        description=(
            "Estimated error bound on Resid Freq: how far off that figure could be."
        ),
    ),
    "offset": TooltipContent(
        description=(
            "Estimated offset from this source, read from the fitted line. Positive "
            "means the local clock is ahead of it."
        ),
    ),
    "offset_err": TooltipContent(
        description=(
            "Estimated error bound on Offset. It covers the uncertainty in the fit "
            "and the source's own root distance, and widens with time since the "
            "last sample."
        ),
    ),
    "reference_id": TooltipContent(
        description=(
            "The source's 32-bit ID in hex. For an IPv4 server it is the address. "
            "For IPv6 it is the first 32 bits of the address's MD5 sum. For a "
            "reference clock it is the clock's name in ASCII."
        ),
    ),
}

# RTC (Real-Time Clock) Field Tooltips
RTC_TOOLTIPS: dict[str, TooltipContent] = {
    "ref_time": TooltipContent(
        description="What the hardware clock read when chronyd last measured its error.",
    ),
    "samples": TooltipContent(
        description=(
            "Past measurements chronyd uses to work out how fast the hardware clock "
            "gains or loses time."
        ),
    ),
    "runs": TooltipContent(
        description=(
            "Runs of same-sign residuals after fitting a line to the hardware "
            "clock's error over time. A low count means a straight line fits badly, "
            "so chronyd deletes older measurements."
        ),
    ),
    "span": TooltipContent(
        description="Time between the oldest and newest measurements in use.",
    ),
    "offset": TooltipContent(
        description=(
            "Estimated error of the hardware clock. Positive means it is ahead, "
            "negative behind. chronyc trimrtc can bring a large error back in line."
        ),
    ),
    "drift_rate": TooltipContent(
        description=(
            "Time the hardware clock gains (positive) or loses (negative) per "
            "second, in parts per million. At +1 ppm it gains 1 µs every second, "
            "about 86 ms a day."
        ),
    ),
}
