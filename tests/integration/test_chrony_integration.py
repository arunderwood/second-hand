"""Integration tests for chrony service with real chronyd."""

import pytest

from second_hand.services.chrony import fetch_chrony_data


@pytest.mark.integration
class TestChronyIntegration:
    """Integration tests requiring a running chronyd instance."""

    def test_fetch_tracking_data(
        self,
        check_chronyd_running: bool,
        chrony_socket_path: str,
    ) -> None:
        """Test fetching tracking data from real chronyd."""
        data = fetch_chrony_data(socket_path=chrony_socket_path)

        assert data.error is None, f"Unexpected error: {data.error}"
        assert data.tracking is not None
        assert data.is_connected is True

    def test_tracking_has_expected_fields(
        self,
        check_chronyd_running: bool,
        chrony_socket_path: str,
    ) -> None:
        """Test that tracking data has all expected fields."""
        data = fetch_chrony_data(socket_path=chrony_socket_path)

        assert data.tracking is not None
        tracking = data.tracking

        # Verify key fields exist and have valid values
        assert isinstance(tracking.stratum, int)
        assert 0 <= tracking.stratum <= 16
        assert isinstance(tracking.offset, float)
        assert isinstance(tracking.reference_id_name, str)

    def test_fetch_sources_data(
        self,
        check_chronyd_running: bool,
        chrony_socket_path: str,
    ) -> None:
        """Test fetching sources list from real chronyd."""
        data = fetch_chrony_data(socket_path=chrony_socket_path)

        assert data.error is None
        # Sources list might be empty if no NTP sources configured
        assert isinstance(data.sources, list)

    def test_sources_have_expected_fields(
        self,
        check_chronyd_running: bool,
        chrony_socket_path: str,
    ) -> None:
        """Test that source data has expected fields when sources exist."""
        data = fetch_chrony_data(socket_path=chrony_socket_path)

        for source in data.sources:
            assert isinstance(source.address, str)
            assert isinstance(source.stratum, int)
            assert isinstance(source.poll, int)
            assert isinstance(source.reachability, int)
            assert 0 <= source.reachability <= 255

    def test_fetch_source_stats_data(
        self,
        check_chronyd_running: bool,
        chrony_socket_path: str,
    ) -> None:
        """Test fetching source statistics from real chronyd."""
        data = fetch_chrony_data(socket_path=chrony_socket_path)

        assert data.error is None
        # Source stats list might be empty if no NTP sources configured
        assert isinstance(data.source_stats, list)

    def test_source_stats_have_expected_fields(
        self,
        check_chronyd_running: bool,
        chrony_socket_path: str,
    ) -> None:
        """Test that source stats have expected fields when they exist."""
        data = fetch_chrony_data(socket_path=chrony_socket_path)

        for stats in data.source_stats:
            assert isinstance(stats.address, str)
            assert isinstance(stats.samples, int)
            assert stats.samples >= 0
            assert isinstance(stats.offset, float)
            assert isinstance(stats.std_dev, float)

    def test_rtc_data_handling(
        self,
        check_chronyd_running: bool,
        chrony_socket_path: str,
    ) -> None:
        """Test RTC data handling (may be None if not configured)."""
        data = fetch_chrony_data(socket_path=chrony_socket_path)

        assert data.error is None
        # RTC data might be None if RTC tracking not configured
        # This is not an error condition
        if data.rtc is not None:
            assert isinstance(data.rtc.offset, float)
            assert isinstance(data.rtc.samples, int)

    def test_chrony_data_properties(
        self,
        check_chronyd_running: bool,
        chrony_socket_path: str,
    ) -> None:
        """Test ChronyData computed properties."""
        data = fetch_chrony_data(socket_path=chrony_socket_path)

        # is_connected should be True when we have tracking data
        assert data.is_connected is True

        # is_synchronized depends on the actual chrony state
        # With local stratum 10, it should be synchronized
        if data.tracking and data.tracking.stratum < 16:
            assert data.is_synchronized is True


@pytest.mark.integration
class TestDashboardIntegration:
    """Integration tests for dashboard with real chronyd."""

    def test_dashboard_renders_with_chrony_data(
        self,
        check_chronyd_running: bool,
        chrony_socket_path: str,
    ) -> None:
        """Test that dashboard renders correctly with real chrony data."""
        from second_hand.components.dashboard import dashboard_page

        data = fetch_chrony_data(socket_path=chrony_socket_path)
        page = dashboard_page(version="test", chrony_data=data)
        html = str(page)

        # Dashboard should render without errors
        assert "<html" in html
        assert "second-hand" in html

        # Should have tracking section
        assert "Time Synchronization" in html

    def test_dashboard_shows_sync_status(
        self,
        check_chronyd_running: bool,
        chrony_socket_path: str,
    ) -> None:
        """Test that dashboard shows synchronization status."""
        from second_hand.components.dashboard import dashboard_page

        data = fetch_chrony_data(socket_path=chrony_socket_path)
        page = dashboard_page(version="test", chrony_data=data)
        html = str(page)

        # Should show either Synchronized or Not Synchronized
        assert "Synchronized" in html

    def test_dashboard_shows_stratum(
        self,
        check_chronyd_running: bool,
        chrony_socket_path: str,
    ) -> None:
        """Test that dashboard shows stratum value."""
        from second_hand.components.dashboard import dashboard_page

        data = fetch_chrony_data(socket_path=chrony_socket_path)
        page = dashboard_page(version="test", chrony_data=data)
        html = str(page)

        # Should show Stratum label
        assert "Stratum" in html
