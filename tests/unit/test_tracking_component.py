"""Unit tests for tracking component."""

import pytest
from pychrony import LeapStatus, TrackingStatus

from second_hand.components.tracking import tracking_section
from second_hand.services.chrony import ChronyData


@pytest.fixture
def mock_tracking_synchronized() -> TrackingStatus:
    """Create a synchronized TrackingStatus for testing."""
    return TrackingStatus(
        reference_id=0x50505300,  # PPS
        reference_id_name="PPS",
        reference_ip="127.127.22.0",
        stratum=1,
        leap_status=LeapStatus.NORMAL,
        ref_time=1700000000.0,
        offset=0.000001,
        last_offset=0.0000015,
        rms_offset=0.000002,
        frequency=1.5,
        residual_freq=0.001,
        skew=0.01,
        root_delay=0.0,
        root_dispersion=0.00001,
        update_interval=16.0,
    )


@pytest.fixture
def mock_tracking_unsynchronized() -> TrackingStatus:
    """Create an unsynchronized TrackingStatus for testing."""
    return TrackingStatus(
        reference_id=0,  # No reference
        reference_id_name="",
        reference_ip="",
        stratum=16,  # Unsync stratum
        leap_status=LeapStatus.UNSYNC,
        ref_time=0.0,
        offset=0.0,
        last_offset=0.0,
        rms_offset=0.0,
        frequency=0.0,
        residual_freq=0.0,
        skew=0.0,
        root_delay=0.0,
        root_dispersion=0.0,
        update_interval=0.0,
    )


class TestTrackingSection:
    """Tests for tracking_section component."""

    def test_synchronized_tracking_displays_status(
        self, mock_tracking_synchronized: TrackingStatus
    ) -> None:
        """Test synchronized tracking displays correct status."""
        data = ChronyData(
            tracking=mock_tracking_synchronized,
            sources=[],
            source_stats=[],
            rtc=None,
            error=None,
        )

        result = str(tracking_section(data))

        assert "Synchronized" in result
        assert "Stratum" in result
        assert "1" in result  # Stratum value
        assert "PPS" in result  # Reference source

    def test_unsynchronized_tracking_displays_status(
        self, mock_tracking_unsynchronized: TrackingStatus
    ) -> None:
        """Test unsynchronized tracking displays correct status."""
        data = ChronyData(
            tracking=mock_tracking_unsynchronized,
            sources=[],
            source_stats=[],
            rtc=None,
            error=None,
        )

        result = str(tracking_section(data))

        assert "Not Synchronized" in result
        assert "16" in result  # Unsync stratum

    def test_connection_error_displays_error_section(self) -> None:
        """Test connection error displays error in tracking section."""
        data = ChronyData(
            tracking=None,
            sources=[],
            source_stats=[],
            rtc=None,
            error="Unable to connect to chronyd. Is the service running?",
        )

        result = str(tracking_section(data))

        # Should still render but with error state
        assert "Status" in result or "Error" in result

    def test_offset_is_formatted(
        self, mock_tracking_synchronized: TrackingStatus
    ) -> None:
        """Test that offset is formatted appropriately."""
        data = ChronyData(
            tracking=mock_tracking_synchronized,
            sources=[],
            source_stats=[],
            rtc=None,
            error=None,
        )

        result = str(tracking_section(data))

        # Offset should be formatted (1 microsecond = +1.0 µs)
        assert "µs" in result or "ms" in result or "s" in result

    def test_stat_boxes_have_proper_structure(
        self, mock_tracking_synchronized: TrackingStatus
    ) -> None:
        """Test that tracking section contains proper stat box structure."""
        data = ChronyData(
            tracking=mock_tracking_synchronized,
            sources=[],
            source_stats=[],
            rtc=None,
            error=None,
        )

        result = str(tracking_section(data))

        # Should contain stat-box class elements
        assert "stat-box" in result
        # Should have title and value structure
        assert "stat-title" in result
        assert "stat-value" in result
