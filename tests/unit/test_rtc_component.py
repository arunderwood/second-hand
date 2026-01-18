"""Unit tests for RTC section component."""

import pytest
from pychrony import RTCData

from second_hand.components.rtc import rtc_section


@pytest.fixture
def mock_rtc() -> RTCData:
    """Create mock RTC data for testing."""
    return RTCData(
        ref_time=1700000000.0,
        samples=10,
        runs=5,
        span=86400,
        offset=0.5,
        freq_offset=1.2,
    )


class TestRtcSection:
    """Tests for rtc_section component."""

    def test_rtc_section_displays_offset(self, mock_rtc: RTCData) -> None:
        """Test RTC section displays offset value."""
        result = str(rtc_section(mock_rtc))

        assert "Offset" in result
        # Should contain the formatted offset
        assert "0.5" in result or "+0.5" in result

    def test_rtc_section_displays_drift(self, mock_rtc: RTCData) -> None:
        """Test RTC section displays drift rate."""
        result = str(rtc_section(mock_rtc))

        assert "Drift" in result
        assert "ppm" in result

    def test_rtc_section_displays_samples(self, mock_rtc: RTCData) -> None:
        """Test RTC section displays sample count."""
        result = str(rtc_section(mock_rtc))

        assert "Samples" in result
        assert "10" in result

    def test_rtc_section_has_title(self, mock_rtc: RTCData) -> None:
        """Test RTC section has proper title."""
        result = str(rtc_section(mock_rtc))

        assert "Hardware RTC" in result or "RTC" in result

    def test_rtc_unavailable_shows_message(self) -> None:
        """Test None RTC shows unavailable message."""
        result = str(rtc_section(None))

        assert "not configured" in result.lower()

    def test_rtc_section_structure(self, mock_rtc: RTCData) -> None:
        """Test RTC section has proper structure."""
        result = str(rtc_section(mock_rtc))

        assert "rtc-section" in result
        assert "rtc-stats" in result
        assert "rtc-stat" in result

    def test_offset_has_sign(self, mock_rtc: RTCData) -> None:
        """Test offset is formatted with sign."""
        result = str(rtc_section(mock_rtc))

        # Positive offset should have + sign
        assert "+0.5" in result or "+0" in result

    def test_drift_has_sign(self, mock_rtc: RTCData) -> None:
        """Test drift is formatted with sign."""
        result = str(rtc_section(mock_rtc))

        # Positive drift should have + sign
        assert "+1.2" in result or "+1" in result
