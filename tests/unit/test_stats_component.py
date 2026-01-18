"""Unit tests for source statistics table component."""

import pytest
from pychrony import SourceStats

from second_hand.components.stats import stats_table


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
        SourceStats(
            reference_id=0x0A000001,
            address="10.0.0.1",
            samples=16,
            runs=8,
            span=512,
            std_dev=0.00005,
            resid_freq=0.005,
            skew=0.0005,
            offset=-0.0005,
            offset_err=0.00005,
        ),
    ]


class TestStatsTable:
    """Tests for stats_table component."""

    def test_stats_table_displays_all_sources(
        self, mock_source_stats: list[SourceStats]
    ) -> None:
        """Test stats table displays all provided sources."""
        result = str(stats_table(mock_source_stats))

        assert "192.168.1.1" in result
        assert "10.0.0.1" in result

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

        assert "8" in result
        assert "16" in result

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
