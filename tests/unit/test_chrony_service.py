"""Unit tests for chrony service."""

from unittest.mock import MagicMock, patch

import pytest
from pychrony import (
    ChronyConnectionError,
    ChronyPermissionError,
    RTCData,
    Source,
    SourceStats,
    TrackingStatus,
)
from pychrony.testing import (
    make_rtc_data,
    make_source,
    make_source_stats,
    make_tracking,
)

from second_hand.services.chrony import ChronyData, fetch_chrony_data


@pytest.fixture
def mock_tracking() -> TrackingStatus:
    """Create a mock TrackingStatus for testing using factory defaults."""
    return make_tracking()


@pytest.fixture
def mock_sources() -> list[Source]:
    """Create mock sources for testing using factory defaults."""
    return [
        make_source(address="192.168.1.1"),
        make_source(address="10.0.0.1", reachability=0),
    ]


@pytest.fixture
def mock_source_stats() -> list[SourceStats]:
    """Create mock source stats for testing using factory defaults."""
    return [make_source_stats(address="192.168.1.1")]


@pytest.fixture
def mock_rtc() -> RTCData:
    """Create mock RTC data for testing using factory defaults."""
    return make_rtc_data()


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

    @patch("second_hand.services.chrony.ChronyConnection")
    def test_fetch_all_data_successfully(
        self,
        mock_connection_class: MagicMock,
        mock_tracking: TrackingStatus,
        mock_sources: list[Source],
        mock_source_stats: list[SourceStats],
        mock_rtc: RTCData,
    ) -> None:
        """Test successful fetch of all chrony data."""
        mock_conn = MagicMock()
        mock_conn.get_tracking.return_value = mock_tracking
        mock_conn.get_sources.return_value = mock_sources
        mock_conn.get_source_stats.return_value = mock_source_stats
        mock_conn.get_rtc_data.return_value = mock_rtc
        mock_connection_class.return_value.__enter__.return_value = mock_conn

        result = fetch_chrony_data()

        assert result.tracking == mock_tracking
        assert result.sources == mock_sources
        assert result.source_stats == mock_source_stats
        assert result.rtc == mock_rtc
        assert result.error is None
        assert result.is_connected is True

    @patch("second_hand.services.chrony.ChronyConnection")
    def test_connection_error_returns_error_data(
        self, mock_connection_class: MagicMock
    ) -> None:
        """Test connection error returns appropriate error message."""
        mock_connection_class.return_value.__enter__.side_effect = (
            ChronyConnectionError("Connection failed")
        )

        result = fetch_chrony_data()

        assert result.tracking is None
        assert result.sources == []
        assert result.source_stats == []
        assert result.rtc is None
        assert result.error == "Unable to connect to chronyd. Is the service running?"
        assert result.is_connected is False

    @patch("second_hand.services.chrony.ChronyConnection")
    def test_permission_error_returns_error_data(
        self, mock_connection_class: MagicMock
    ) -> None:
        """Test permission error returns appropriate error message."""
        mock_connection_class.return_value.__enter__.side_effect = (
            ChronyPermissionError("Permission denied")
        )

        result = fetch_chrony_data()

        assert result.tracking is None
        assert result.error == "Permission denied. Add your user to the chrony group."
        assert result.is_connected is False

    @patch("second_hand.services.chrony.ChronyConnection")
    def test_rtc_unavailable_returns_none(
        self,
        mock_connection_class: MagicMock,
        mock_tracking: TrackingStatus,
        mock_sources: list[Source],
        mock_source_stats: list[SourceStats],
    ) -> None:
        """Test that RTC unavailable returns None without error."""
        mock_conn = MagicMock()
        mock_conn.get_tracking.return_value = mock_tracking
        mock_conn.get_sources.return_value = mock_sources
        mock_conn.get_source_stats.return_value = mock_source_stats
        mock_conn.get_rtc_data.return_value = None  # RTC not available
        mock_connection_class.return_value.__enter__.return_value = mock_conn

        result = fetch_chrony_data()

        assert result.tracking == mock_tracking
        assert result.sources == mock_sources
        assert result.source_stats == mock_source_stats
        assert result.rtc is None
        assert result.error is None
        assert result.is_connected is True

    @patch("second_hand.services.chrony.ChronyConnection")
    def test_custom_socket_path_passed_to_connection(
        self, mock_connection_class: MagicMock
    ) -> None:
        """Test custom socket path is passed to ChronyConnection."""
        mock_connection_class.return_value.__enter__.side_effect = (
            ChronyConnectionError("No connection")
        )

        fetch_chrony_data(socket_path="/custom/socket.sock")

        mock_connection_class.assert_called_once_with("/custom/socket.sock")
