"""Unit tests for chrony service."""

from unittest.mock import MagicMock, patch

import pytest
from pychrony import (
    ChronyConnectionError,
    ChronyDataError,
    ChronyPermissionError,
    LeapStatus,
    RTCData,
    Source,
    SourceMode,
    SourceState,
    SourceStats,
    TrackingStatus,
)

from second_hand.services.chrony import ChronyData, fetch_chrony_data


@pytest.fixture
def mock_tracking() -> TrackingStatus:
    """Create a mock TrackingStatus for testing."""
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
def mock_sources() -> list[Source]:
    """Create mock sources for testing."""
    return [
        Source(
            address="192.168.1.1",
            poll=6,
            stratum=2,
            state=SourceState.SELECTED,
            mode=SourceMode.CLIENT,
            flags=0,
            reachability=255,
            last_sample_ago=5,
            orig_latest_meas=0.001,
            latest_meas=0.001,
            latest_meas_err=0.0001,
        ),
        Source(
            address="10.0.0.1",
            poll=6,
            stratum=3,
            state=SourceState.UNSELECTED,
            mode=SourceMode.CLIENT,
            flags=0,
            reachability=0,
            last_sample_ago=120,
            orig_latest_meas=0.005,
            latest_meas=0.005,
            latest_meas_err=0.001,
        ),
    ]


@pytest.fixture
def mock_source_stats() -> list[SourceStats]:
    """Create mock source stats for testing."""
    return [
        SourceStats(
            reference_id=0xC0A80101,
            address="192.168.1.1",
            samples=8,
            runs=4,
            span=256,
            std_dev=0.0001,
            resid_freq=0.01,
            skew=0.001,
            offset=0.001,
            offset_err=0.0001,
        ),
    ]


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


class TestChronyData:
    """Tests for ChronyData dataclass."""

    def test_is_connected_when_tracking_and_no_error(
        self, mock_tracking: TrackingStatus
    ) -> None:
        """Test is_connected returns True when tracking exists and no error."""
        data = ChronyData(
            tracking=mock_tracking,
            sources=[],
            source_stats=[],
            rtc=None,
            error=None,
        )
        assert data.is_connected is True

    def test_is_connected_false_when_error(self, mock_tracking: TrackingStatus) -> None:
        """Test is_connected returns False when error exists."""
        data = ChronyData(
            tracking=mock_tracking,
            sources=[],
            source_stats=[],
            rtc=None,
            error="Some error",
        )
        assert data.is_connected is False

    def test_is_connected_false_when_no_tracking(self) -> None:
        """Test is_connected returns False when tracking is None."""
        data = ChronyData(
            tracking=None,
            sources=[],
            source_stats=[],
            rtc=None,
            error=None,
        )
        assert data.is_connected is False

    def test_is_synchronized_when_tracking_synchronized(
        self, mock_tracking: TrackingStatus
    ) -> None:
        """Test is_synchronized returns True when tracking is synchronized."""
        data = ChronyData(
            tracking=mock_tracking,
            sources=[],
            source_stats=[],
            rtc=None,
            error=None,
        )
        assert data.is_synchronized is True

    def test_is_synchronized_false_when_no_tracking(self) -> None:
        """Test is_synchronized returns False when tracking is None."""
        data = ChronyData(
            tracking=None,
            sources=[],
            source_stats=[],
            rtc=None,
            error=None,
        )
        assert data.is_synchronized is False


class TestFetchChronyData:
    """Tests for fetch_chrony_data function."""

    @patch("second_hand.services.chrony.get_rtc_data")
    @patch("second_hand.services.chrony.get_source_stats")
    @patch("second_hand.services.chrony.get_sources")
    @patch("second_hand.services.chrony.get_tracking")
    def test_fetch_all_data_successfully(
        self,
        mock_get_tracking: MagicMock,
        mock_get_sources: MagicMock,
        mock_get_source_stats: MagicMock,
        mock_get_rtc_data: MagicMock,
        mock_tracking: TrackingStatus,
        mock_sources: list[Source],
        mock_source_stats: list[SourceStats],
        mock_rtc: RTCData,
    ) -> None:
        """Test successful fetch of all chrony data."""
        mock_get_tracking.return_value = mock_tracking
        mock_get_sources.return_value = mock_sources
        mock_get_source_stats.return_value = mock_source_stats
        mock_get_rtc_data.return_value = mock_rtc

        result = fetch_chrony_data()

        assert result.tracking == mock_tracking
        assert result.sources == mock_sources
        assert result.source_stats == mock_source_stats
        assert result.rtc == mock_rtc
        assert result.error is None
        assert result.is_connected is True

    @patch("second_hand.services.chrony.get_tracking")
    def test_connection_error_returns_error_data(
        self, mock_get_tracking: MagicMock
    ) -> None:
        """Test connection error returns appropriate error message."""
        mock_get_tracking.side_effect = ChronyConnectionError("Connection failed")

        result = fetch_chrony_data()

        assert result.tracking is None
        assert result.sources == []
        assert result.source_stats == []
        assert result.rtc is None
        assert result.error == "Unable to connect to chronyd. Is the service running?"
        assert result.is_connected is False

    @patch("second_hand.services.chrony.get_tracking")
    def test_permission_error_returns_error_data(
        self, mock_get_tracking: MagicMock
    ) -> None:
        """Test permission error returns appropriate error message."""
        mock_get_tracking.side_effect = ChronyPermissionError("Permission denied")

        result = fetch_chrony_data()

        assert result.tracking is None
        assert result.error == "Permission denied. Add your user to the chrony group."
        assert result.is_connected is False

    @patch("second_hand.services.chrony.get_rtc_data")
    @patch("second_hand.services.chrony.get_source_stats")
    @patch("second_hand.services.chrony.get_sources")
    @patch("second_hand.services.chrony.get_tracking")
    def test_rtc_unavailable_is_not_error(
        self,
        mock_get_tracking: MagicMock,
        mock_get_sources: MagicMock,
        mock_get_source_stats: MagicMock,
        mock_get_rtc_data: MagicMock,
        mock_tracking: TrackingStatus,
        mock_sources: list[Source],
        mock_source_stats: list[SourceStats],
    ) -> None:
        """Test that RTC unavailable is handled gracefully without error."""
        mock_get_tracking.return_value = mock_tracking
        mock_get_sources.return_value = mock_sources
        mock_get_source_stats.return_value = mock_source_stats
        mock_get_rtc_data.side_effect = ChronyDataError("RTC not available")

        result = fetch_chrony_data()

        assert result.tracking == mock_tracking
        assert result.sources == mock_sources
        assert result.source_stats == mock_source_stats
        assert result.rtc is None
        assert result.error is None
        assert result.is_connected is True

    @patch("second_hand.services.chrony.get_tracking")
    def test_custom_socket_path_passed_to_pychrony(
        self, mock_get_tracking: MagicMock
    ) -> None:
        """Test custom socket path is passed to pychrony functions."""
        mock_get_tracking.side_effect = ChronyConnectionError("No connection")

        fetch_chrony_data(socket_path="/custom/socket.sock")

        mock_get_tracking.assert_called_once_with(socket_path="/custom/socket.sock")
