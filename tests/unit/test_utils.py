"""Tests for utility functions."""

from second_hand.utils import (
    format_duration,
    format_frequency,
    format_offset,
    format_reachability,
    format_reachability_visual,
    format_timestamp,
    get_health_status,
)


class TestFormatOffset:
    """Tests for format_offset function."""

    def test_positive_seconds(self) -> None:
        assert format_offset(1.234) == "+1.234 s"

    def test_negative_seconds(self) -> None:
        assert format_offset(-2.5) == "-2.500 s"

    def test_positive_milliseconds(self) -> None:
        assert format_offset(0.01234) == "+12.340 ms"

    def test_negative_milliseconds(self) -> None:
        assert format_offset(-0.05) == "-50.000 ms"

    def test_positive_microseconds(self) -> None:
        assert format_offset(0.0001234) == "+123.4 \u00b5s"

    def test_negative_microseconds(self) -> None:
        assert format_offset(-0.000050) == "-50.0 \u00b5s"

    def test_positive_nanoseconds(self) -> None:
        assert format_offset(0.000000123) == "+123 ns"

    def test_negative_nanoseconds(self) -> None:
        assert format_offset(-0.000000500) == "-500 ns"

    def test_zero_offset(self) -> None:
        assert format_offset(0.0) == "+0 ns"


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_seconds_only(self) -> None:
        assert format_duration(45) == "45s"

    def test_minutes_and_seconds(self) -> None:
        assert format_duration(125) == "2m 5s"

    def test_hours_and_minutes(self) -> None:
        assert format_duration(3723) == "1h 2m"

    def test_exactly_one_minute(self) -> None:
        assert format_duration(60) == "1m 0s"

    def test_exactly_one_hour(self) -> None:
        assert format_duration(3600) == "1h 0m"


class TestFormatReachability:
    """Tests for format_reachability function."""

    def test_full_reachability(self) -> None:
        assert format_reachability(255) == "377"

    def test_zero_reachability(self) -> None:
        assert format_reachability(0) == "000"

    def test_partial_reachability(self) -> None:
        assert format_reachability(127) == "177"


class TestFormatTimestamp:
    """Tests for format_timestamp function."""

    def test_epoch_zero(self) -> None:
        assert format_timestamp(0.0) == "1970-01-01 00:00:00 UTC"

    def test_specific_timestamp(self) -> None:
        # 2026-01-20 12:30:45 UTC = 1768912245
        assert format_timestamp(1768912245.0) == "2026-01-20 12:30:45 UTC"

    def test_timestamp_with_fractional_seconds(self) -> None:
        # Fractional seconds should be truncated
        result = format_timestamp(1768912245.999)
        assert result == "2026-01-20 12:30:45 UTC"


class TestFormatFrequency:
    """Tests for format_frequency function."""

    def test_positive_frequency(self) -> None:
        assert format_frequency(12.345) == "+12.345 ppm"

    def test_negative_frequency(self) -> None:
        assert format_frequency(-0.123) == "-0.123 ppm"

    def test_zero_frequency(self) -> None:
        assert format_frequency(0.0) == "+0.000 ppm"


class TestFormatReachabilityVisual:
    """Tests for format_reachability_visual function."""

    def test_full_reachability(self) -> None:
        # 377 octal = 255 decimal = all 8 bits set
        result = format_reachability_visual(255)
        assert result == [True] * 8

    def test_zero_reachability(self) -> None:
        # 000 octal = 0 decimal = no bits set
        result = format_reachability_visual(0)
        assert result == [False] * 8

    def test_partial_reachability(self) -> None:
        # 177 octal = 127 decimal = 0111 1111
        result = format_reachability_visual(127)
        assert result == [False, True, True, True, True, True, True, True]

    def test_alternating_bits(self) -> None:
        # 170 octal = 120 decimal = 0111 1000
        result = format_reachability_visual(0o170)
        # Binary: 01111000 -> [0,1,1,1,1,0,0,0]
        assert result == [False, True, True, True, True, False, False, False]


class TestGetHealthStatus:
    """Tests for get_health_status function."""

    def test_offset_healthy(self) -> None:
        assert get_health_status("offset", 0.005) == "healthy"

    def test_offset_warning(self) -> None:
        assert get_health_status("offset", 0.050) == "warning"

    def test_offset_error(self) -> None:
        assert get_health_status("offset", 0.200) == "error"

    def test_offset_negative_uses_abs_value(self) -> None:
        assert get_health_status("offset", -0.005) == "healthy"

    def test_stratum_healthy(self) -> None:
        assert get_health_status("stratum", 2) == "healthy"

    def test_stratum_warning(self) -> None:
        assert get_health_status("stratum", 5) == "warning"

    def test_stratum_error(self) -> None:
        assert get_health_status("stratum", 10) == "error"

    def test_stratum_16_is_error(self) -> None:
        # Stratum 16 means unsynchronized
        assert get_health_status("stratum", 16) == "error"

    def test_reachability_healthy(self) -> None:
        assert get_health_status("reachability", 255) == "healthy"

    def test_reachability_warning(self) -> None:
        # 177 octal = 127 decimal, some packet loss
        assert get_health_status("reachability", 200) == "warning"

    def test_reachability_error(self) -> None:
        # High packet loss
        assert get_health_status("reachability", 50) == "error"

    def test_frequency_healthy(self) -> None:
        assert get_health_status("frequency", 5.0) == "healthy"

    def test_frequency_warning(self) -> None:
        assert get_health_status("frequency", 25.0) == "warning"

    def test_frequency_error(self) -> None:
        assert get_health_status("frequency", 100.0) == "error"

    def test_rms_offset_healthy(self) -> None:
        assert get_health_status("rms_offset", 0.0005) == "healthy"

    def test_rms_offset_warning(self) -> None:
        assert get_health_status("rms_offset", 0.005) == "warning"

    def test_rms_offset_error(self) -> None:
        assert get_health_status("rms_offset", 0.050) == "error"

    def test_unknown_metric_defaults_to_healthy(self) -> None:
        assert get_health_status("unknown_metric", 999.0) == "healthy"
