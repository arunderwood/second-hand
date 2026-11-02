"""Unit tests for chrony service."""

import asyncio
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from pychrony import (
    ChronyConnectionError,
    ChronyDataError,
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

import second_hand.services.chrony as chrony_service
from second_hand.services.chrony import (
    ChronyData,
    EnrichedSource,
    enrich_sources,
    fetch_chrony_data,
)
from second_hand.services.geoip import GeoIPResult, GeoIPService
from second_hand.services.rdns import ReverseDNSResult, ReverseDNSService


@pytest.fixture(autouse=True)
def no_rtc_error_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start each test with no RTC error already logged by an earlier one."""
    monkeypatch.setattr(chrony_service, "_last_rtc_error", None)


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
        assert result.error == (
            "Permission denied connecting to chronyd at 127.0.0.1:323. "
            "Check that chronyd's command port is reachable."
        )
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
    def test_rtc_rejected_keeps_the_rest(
        self,
        mock_connection_class: MagicMock,
        mock_tracking: TrackingStatus,
        mock_sources: list[Source],
        mock_source_stats: list[SourceStats],
    ) -> None:
        """A rejected RTC request leaves only the RTC panel empty."""
        mock_conn = MagicMock()
        mock_conn.get_tracking.return_value = mock_tracking
        mock_conn.get_sources.return_value = mock_sources
        mock_conn.get_source_stats.return_value = mock_source_stats
        mock_conn.get_rtc_data.side_effect = ChronyDataError("unauthorized")
        mock_connection_class.return_value.__enter__.return_value = mock_conn

        result = fetch_chrony_data()

        assert result.tracking == mock_tracking
        assert result.sources == mock_sources
        assert result.rtc is None
        assert result.rtc_error == "unauthorized"
        assert result.error is None

    @patch("second_hand.services.chrony.ChronyConnection")
    def test_repeated_rtc_error_warns_once(
        self, mock_connection_class: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A lasting RTC fault warns on the first fetch, and again once it recurs."""
        mock_conn = MagicMock()
        mock_conn.get_rtc_data.side_effect = ChronyDataError("unauthorized")
        mock_connection_class.return_value.__enter__.return_value = mock_conn
        caplog.set_level("WARNING", logger="second_hand.services.chrony")

        fetch_chrony_data()
        fetch_chrony_data()
        assert len(caplog.records) == 1

        mock_conn.get_rtc_data.side_effect = None
        mock_conn.get_rtc_data.return_value = None
        fetch_chrony_data()
        mock_conn.get_rtc_data.side_effect = ChronyDataError("unauthorized")
        fetch_chrony_data()
        assert len(caplog.records) == 2

    @patch("second_hand.services.chrony.ChronyConnection")
    def test_rtc_connection_error_reports_disconnected(
        self,
        mock_connection_class: MagicMock,
        mock_tracking: TrackingStatus,
    ) -> None:
        """chronyd going silent at the RTC request is a lost connection."""
        mock_conn = MagicMock()
        mock_conn.get_tracking.return_value = mock_tracking
        mock_conn.get_rtc_data.side_effect = ChronyConnectionError("timed out")
        mock_connection_class.return_value.__enter__.return_value = mock_conn

        result = fetch_chrony_data()

        assert result.tracking is None
        assert result.error is not None
        assert result.is_connected is False

    @patch("second_hand.services.chrony.ChronyConnection")
    def test_custom_address_passed_to_connection(
        self, mock_connection_class: MagicMock
    ) -> None:
        """Test a custom address is passed through to ChronyConnection."""
        mock_connection_class.return_value.__enter__.side_effect = (
            ChronyConnectionError("No connection")
        )

        fetch_chrony_data(address="/custom/socket.sock")

        mock_connection_class.assert_called_once_with("/custom/socket.sock")

    @patch("second_hand.services.chrony.ChronyConnection")
    def test_defaults_to_configured_address_never_autodetect(
        self, mock_connection_class: MagicMock
    ) -> None:
        """Test the default is an explicit address rather than auto-detect.

        Auto-detect can settle on an unreachable Unix socket without falling
        back to the command port, so the default must stay explicit.
        """
        mock_connection_class.return_value.__enter__.side_effect = (
            ChronyConnectionError("No connection")
        )

        fetch_chrony_data()

        mock_connection_class.assert_called_once_with("127.0.0.1:323")


class TestEnrichSources:
    """Tests for combining GeoIP and reverse DNS onto sources."""

    @staticmethod
    def _enrich(
        sources: list[Source],
        countries: dict[str, str] | None = None,
        hostnames: dict[str, str] | None = None,
    ) -> list[EnrichedSource]:
        """Enrich with stub services that answer from the given mappings."""
        countries = countries or {}
        hostnames = hostnames or {}

        class StubGeoIP(GeoIPService):
            async def lookup(self, ip: str) -> GeoIPResult:
                code = countries.get(ip)
                return GeoIPResult(
                    ip_address=ip,
                    is_private=code is None,
                    country_code=code,
                    country_name="Germany" if code else None,
                )

        class StubRdns(ReverseDNSService):
            async def lookup(self, ip: str) -> ReverseDNSResult:
                return ReverseDNSResult(ip_address=ip, hostname=hostnames.get(ip))

        geoip = StubGeoIP(cast(Any, None))
        return asyncio.run(enrich_sources(sources, geoip, StubRdns(None)))

    def test_hostname_is_attached(self) -> None:
        sources = [make_source(address="8.8.8.8")]

        enriched = self._enrich(sources, hostnames={"8.8.8.8": "dns.google"})

        assert enriched[0].hostname == "dns.google"
        assert enriched[0].display_name == "dns.google"

    def test_unresolved_source_falls_back_to_address(self) -> None:
        enriched = self._enrich([make_source(address="8.8.8.8")])

        assert enriched[0].hostname is None
        assert enriched[0].display_name == "8.8.8.8"

    def test_country_and_hostname_are_combined(self) -> None:
        enriched = self._enrich(
            [make_source(address="8.8.8.8")],
            countries={"8.8.8.8": "DE"},
            hostnames={"8.8.8.8": "dns.google"},
        )

        assert enriched[0].country_code == "DE"
        assert enriched[0].country_flag == "\U0001f1e9\U0001f1ea"
        assert enriched[0].hostname == "dns.google"

    def test_chrony_order_is_preserved(self) -> None:
        sources = [
            make_source(address="8.8.8.8"),
            make_source(address="1.1.1.1"),
            make_source(address="9.9.9.9"),
        ]

        enriched = self._enrich(sources, hostnames={"1.1.1.1": "one.one.one.one"})

        assert [e.source.address for e in enriched] == [
            "8.8.8.8",
            "1.1.1.1",
            "9.9.9.9",
        ]
        assert [e.hostname for e in enriched] == [None, "one.one.one.one", None]

    def test_duplicate_addresses_both_get_the_name(self) -> None:
        """chrony can report the same address twice; both rows need the name."""
        sources = [make_source(address="8.8.8.8"), make_source(address="8.8.8.8")]

        enriched = self._enrich(sources, hostnames={"8.8.8.8": "dns.google"})

        assert [e.hostname for e in enriched] == ["dns.google", "dns.google"]

    def test_no_sources_needs_no_lookups(self) -> None:
        assert self._enrich([]) == []
