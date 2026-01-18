"""Unit tests for sources table component."""

import pytest
from pychrony import Source, SourceMode, SourceState

from second_hand.components.sources import sources_table


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
            poll=8,
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


class TestSourcesTable:
    """Tests for sources_table component."""

    def test_sources_table_displays_all_sources(
        self, mock_sources: list[Source]
    ) -> None:
        """Test sources table displays all provided sources."""
        result = str(sources_table(mock_sources))

        assert "192.168.1.1" in result
        assert "10.0.0.1" in result

    def test_sources_table_has_correct_columns(
        self, mock_sources: list[Source]
    ) -> None:
        """Test sources table has all required column headers."""
        result = str(sources_table(mock_sources))

        assert "Address" in result
        assert "State" in result
        assert "Stratum" in result
        assert "Poll" in result
        assert "Reach" in result
        assert "Last Rx" in result

    def test_selected_source_has_selected_class(
        self, mock_sources: list[Source]
    ) -> None:
        """Test selected source row has selected class."""
        result = str(sources_table(mock_sources))

        # Selected source should have .selected class
        assert "selected" in result

    def test_unreachable_source_has_unreachable_class(
        self, mock_sources: list[Source]
    ) -> None:
        """Test unreachable source row has unreachable class."""
        result = str(sources_table(mock_sources))

        # Unreachable source should have .unreachable class
        assert "unreachable" in result

    def test_reachability_formatted_as_octal(self, mock_sources: list[Source]) -> None:
        """Test reachability is formatted as three-digit octal."""
        result = str(sources_table(mock_sources))

        # 255 in octal is 377
        assert "377" in result
        # 0 in octal is 000
        assert "000" in result

    def test_poll_formatted_as_duration(self, mock_sources: list[Source]) -> None:
        """Test poll interval is formatted as duration."""
        result = str(sources_table(mock_sources))

        # 2^6 = 64 seconds = 1m 4s
        assert "1m" in result
        # 2^8 = 256 seconds = 4m 16s
        assert "4m" in result

    def test_empty_sources_shows_message(self) -> None:
        """Test empty sources list shows appropriate message."""
        result = str(sources_table([]))

        assert "No sources configured" in result

    def test_state_formatted_properly(self, mock_sources: list[Source]) -> None:
        """Test source state is formatted with proper capitalization."""
        result = str(sources_table(mock_sources))

        # Should have proper case formatting
        assert "Selected" in result
        assert "Unselected" in result
