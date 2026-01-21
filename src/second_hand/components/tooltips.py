"""Tooltip content definitions for NTP/chrony fields.

Centralized storage for tooltip text used throughout the dashboard.
Content sourced from chrony documentation and NTP best practices.
"""

from dataclasses import dataclass

__all__ = [
    "TooltipContent",
    "TRACKING_TOOLTIPS",
    "SOURCE_TOOLTIPS",
    "STATS_TOOLTIPS",
    "RTC_TOOLTIPS",
]


@dataclass(frozen=True)
class TooltipContent:
    """Container for tooltip text with optional threshold guidance."""

    description: str
    good_values: str | None = None
    bad_values: str | None = None


# Tracking Status Field Tooltips
TRACKING_TOOLTIPS: dict[str, TooltipContent] = {
    "reference": TooltipContent(
        description=(
            "Currently selected time source. Shows name if resolvable, "
            "otherwise IP address or reference ID."
        ),
    ),
    "reference_ip": TooltipContent(
        description="IP address of the reference time source.",
    ),
    "stratum": TooltipContent(
        description=(
            "Number of hops from a reference clock. Stratum 1 is directly "
            "connected to a reference. Lower is better, 16 means unsynchronized."
        ),
        good_values="1-3",
        bad_values="9+ or 16 (unsynchronized)",
    ),
    "leap_status": TooltipContent(
        description=(
            "Indicates pending leap second adjustments. "
            "Normal means no leap second scheduled."
        ),
        good_values="Normal",
        bad_values="Not synchronised",
    ),
    "ref_time": TooltipContent(
        description=(
            "Timestamp of the last measurement from the reference source. "
            "Should update regularly."
        ),
    ),
    "offset": TooltipContent(
        description=(
            "Current difference between local clock and reference time. "
            "Positive means local clock is ahead."
        ),
        good_values="< 10 ms",
        bad_values="> 100 ms",
    ),
    "last_offset": TooltipContent(
        description=(
            "Offset measured at the most recent clock update. "
            "Shows latest adjustment magnitude."
        ),
        good_values="< 10 ms",
        bad_values="> 100 ms",
    ),
    "rms_offset": TooltipContent(
        description=(
            "Root mean square of recent offset measurements. "
            "Indicates long-term stability."
        ),
        good_values="< 1 ms",
        bad_values="> 10 ms",
    ),
    "frequency": TooltipContent(
        description=(
            "Rate at which the system clock gains or loses time, "
            "in parts per million. Corrected automatically."
        ),
        good_values="< 10 ppm",
        bad_values="> 50 ppm (hardware issue)",
    ),
    "residual_freq": TooltipContent(
        description=(
            "Difference between measured frequency and the value currently "
            "being used. Should approach zero."
        ),
        good_values="< 1 ppm",
    ),
    "skew": TooltipContent(
        description=(
            "Estimated error bound on the frequency measurement. "
            "Lower values indicate more reliable frequency tracking."
        ),
        good_values="< 1 ppm",
        bad_values="> 5 ppm",
    ),
    "root_delay": TooltipContent(
        description=(
            "Total network round-trip delay to the stratum-1 source. "
            "Includes all hops in the path."
        ),
        good_values="< 50 ms",
        bad_values="> 100 ms",
    ),
    "root_dispersion": TooltipContent(
        description=(
            "Accumulated measurement uncertainty through all hops to stratum-1. "
            "Lower is better."
        ),
        good_values="< 10 ms",
        bad_values="> 50 ms",
    ),
    "update_interval": TooltipContent(
        description=(
            "Time since the last successful clock update. "
            "Depends on polling configuration."
        ),
    ),
}

# Source Field Tooltips
SOURCE_TOOLTIPS: dict[str, TooltipContent] = {
    "mode": TooltipContent(
        description=(
            "Source type: ^ = server (client mode), "
            "= = peer (symmetric), # = local reference clock."
        ),
    ),
    "state": TooltipContent(
        description=(
            "Selection status: * = selected best, + = combined, "
            "- = selectable but unused, ? = unusable, "
            "x = falseticker (rejected), ~ = high variability."
        ),
    ),
    "address": TooltipContent(
        description="Network address or reference ID of the time source.",
    ),
    "stratum": TooltipContent(
        description=(
            "Stratum level reported by this source. "
            "Lower means closer to a reference clock."
        ),
        good_values="1-3",
        bad_values="9+",
    ),
    "poll": TooltipContent(
        description=(
            "Current polling interval as a power of 2 seconds. "
            "Example: 6 = 64 seconds between queries."
        ),
    ),
    "reach": TooltipContent(
        description=(
            "Reachability register (octal). Each bit represents one of "
            "the last 8 polls. 377 = all successful, 0 = unreachable."
        ),
        good_values="377 (all 8 successful)",
        bad_values="< 177 (high packet loss)",
    ),
    "last_rx": TooltipContent(
        description="Time since the last valid response was received from this source.",
    ),
    "latest_meas": TooltipContent(
        description=(
            "Most recent offset measurement from this source, "
            "showing the time difference."
        ),
    ),
    "latest_meas_err": TooltipContent(
        description=(
            "Estimated error bound on the latest measurement. Smaller is better."
        ),
    ),
    "orig_latest_meas": TooltipContent(
        description="Original (unadjusted) latest measurement from this source.",
    ),
}

# Source Statistics Field Tooltips
STATS_TOOLTIPS: dict[str, TooltipContent] = {
    "samples": TooltipContent(
        description=(
            "Number of sample points currently retained for statistical analysis. "
            "More samples = better estimates."
        ),
    ),
    "runs": TooltipContent(
        description=(
            "Number of runs of residuals with the same sign. "
            "Should be roughly half of samples for a good linear fit."
        ),
    ),
    "span": TooltipContent(
        description=(
            "Time interval covered by the retained samples. "
            "Longer spans improve frequency estimation."
        ),
    ),
    "std_dev": TooltipContent(
        description=(
            "Standard deviation of offset measurements. "
            "Indicates measurement noise level. Lower is better."
        ),
        good_values="< 50 us",
        bad_values="> 1 ms",
    ),
    "resid_freq": TooltipContent(
        description="Residual frequency estimate for this source in parts per million.",
    ),
    "skew": TooltipContent(
        description="Estimated error bound on the frequency measurement from this source.",
    ),
    "offset": TooltipContent(
        description="Estimated current offset of this source from true time.",
    ),
    "offset_err": TooltipContent(
        description="Estimated error bound on the offset measurement.",
    ),
    "reference_id": TooltipContent(
        description="Reference ID of the source, typically displayed as hex.",
    ),
}

# RTC (Real-Time Clock) Field Tooltips
RTC_TOOLTIPS: dict[str, TooltipContent] = {
    "ref_time": TooltipContent(
        description="Timestamp of the last RTC error measurement.",
    ),
    "samples": TooltipContent(
        description=(
            "Number of measurements used to estimate RTC drift rate. "
            "More samples = better calibration."
        ),
    ),
    "runs": TooltipContent(
        description=(
            "Number of residual runs. "
            "Indicates how well measurements fit a linear model."
        ),
    ),
    "span": TooltipContent(
        description=(
            "Time period covered by RTC measurements. "
            "Longer spans improve drift estimates."
        ),
    ),
    "offset": TooltipContent(
        description="Current estimated RTC error (how much the RTC is fast or slow).",
    ),
    "drift_rate": TooltipContent(
        description="Rate at which the RTC gains or loses time, in parts per million.",
    ),
}
