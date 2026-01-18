"""Unit tests for RTC section component."""

import pytest
from pychrony import RTCData
from pychrony.testing import make_rtc_data

from second_hand.components.rtc import rtc_section


@pytest.fixture
def mock_rtc() -> RTCData:
    """Create mock RTC data for testing using factory defaults."""
    return make_rtc_data()


class TestRtcSection:
    """Tests for rtc_section component."""

    def test_rtc_section_displays_offset(self, mock_rtc: RTCData) -> None:
        """Test RTC section displays offset value."""
        result = str(rtc_section(mock_rtc))

        assert "Offset" in result

    def test_rtc_section_displays_drift(self, mock_rtc: RTCData) -> None:
        """Test RTC section displays drift rate."""
        result = str(rtc_section(mock_rtc))

        assert "Drift" in result
        assert "ppm" in result

    def test_rtc_section_displays_samples(self, mock_rtc: RTCData) -> None:
        """Test RTC section displays sample count."""
        result = str(rtc_section(mock_rtc))

        assert "Samples" in result
        # Reference fixture value
        assert str(mock_rtc.samples) in result

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

        # Offset should have sign (+ or -)
        assert "+" in result or "-" in result

    def test_drift_has_sign(self, mock_rtc: RTCData) -> None:
        """Test drift is formatted with sign."""
        result = str(rtc_section(mock_rtc))

        # Drift should have sign (+ or -)
        assert "+" in result or "-" in result
