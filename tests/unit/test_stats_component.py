"""Unit tests for source statistics table component."""

import pytest
from pychrony import SourceStats
from pychrony.testing import make_source_stats

from second_hand.components.stats import stats_table


@pytest.fixture
def mock_source_stats() -> list[SourceStats]:
    """Create mock source stats for testing using factory defaults."""
    return [
        make_source_stats(address="192.168.1.1", samples=8),
        make_source_stats(address="10.0.0.1", samples=16),
    ]


class TestStatsTable:
    """Tests for stats_table component."""

    def test_stats_table_displays_all_sources(
        self, mock_source_stats: list[SourceStats]
    ) -> None:
        """Test stats table displays all provided sources."""
        result = str(stats_table(mock_source_stats))

        for stats in mock_source_stats:
            assert stats.address in result

    def test_stats_table_has_correct_columns(
        self, mock_source_stats: list[SourceStats]
    ) -> None:
        """Test stats table has all required column headers."""
        result = str(stats_table(mock_source_stats))

        assert "Address" in result
        assert "Samples" in result
        assert "Offset" in result
        assert "Std Dev" in result
        assert "Skew" in result

    def test_samples_displayed_as_integer(
        self, mock_source_stats: list[SourceStats]
    ) -> None:
        """Test samples count is displayed as integer."""
        result = str(stats_table(mock_source_stats))

        # Reference fixture values
        for stats in mock_source_stats:
            assert str(stats.samples) in result

    def test_offset_formatted_with_units(
        self, mock_source_stats: list[SourceStats]
    ) -> None:
        """Test offset is formatted with appropriate units."""
        result = str(stats_table(mock_source_stats))

        # Offsets should have units (ms or µs)
        assert "ms" in result or "µs" in result

    def test_std_dev_in_scientific_notation(
        self, mock_source_stats: list[SourceStats]
    ) -> None:
        """Test standard deviation is displayed in scientific notation."""
        result = str(stats_table(mock_source_stats))

        # Scientific notation indicator
        assert "e-" in result.lower()

    def test_skew_formatted_with_ppm(
        self, mock_source_stats: list[SourceStats]
    ) -> None:
        """Test skew is formatted with ppm unit."""
        result = str(stats_table(mock_source_stats))

        assert "ppm" in result

    def test_empty_stats_shows_message(self) -> None:
        """Test empty stats list shows appropriate message."""
        result = str(stats_table([]))

        assert "No statistics available" in result

    def test_table_structure_correct(
        self, mock_source_stats: list[SourceStats]
    ) -> None:
        """Test table has proper structure."""
        result = str(stats_table(mock_source_stats))

        assert "data-table" in result
        assert "<thead>" in result
        assert "<tbody>" in result
