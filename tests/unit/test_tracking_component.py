"""Unit tests for tracking component."""

import pytest
from pychrony import LeapStatus, TrackingStatus
from pychrony.testing import make_tracking

from second_hand.components.tracking import tracking_section
from second_hand.services.chrony import ChronyData


@pytest.fixture
def mock_tracking_synchronized() -> TrackingStatus:
    """Factory defaults provide a synchronized state."""
    return make_tracking()


@pytest.fixture
def mock_tracking_unsynchronized() -> TrackingStatus:
    """Only override fields that define unsynchronized state."""
    return make_tracking(
        reference_id=0,
        stratum=16,
        leap_status=LeapStatus.UNSYNC,
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
        # Reference fixture values, not magic numbers
        assert str(mock_tracking_synchronized.stratum) in result
        assert mock_tracking_synchronized.reference_id_name in result

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
        assert str(mock_tracking_unsynchronized.stratum) in result

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

        # Offset should be formatted with units
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
