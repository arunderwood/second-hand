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


class TestReferenceClockLabel:
    """Tests for naming rows that chronyd reports without an address."""

    @pytest.mark.parametrize(
        ("reference_id", "expected"),
        [
            (0x4E4D4541, "NMEA"),
            (0x50505300, "PPS"),
            (0x47505300, "GPS"),
        ],
    )
    def test_refclock_named_from_reference_id(
        self, reference_id: int, expected: str
    ) -> None:
        """A reference clock is labelled with its four-character name."""
        stats = make_source_stats(address="", reference_id=reference_id)

        result = str(stats_table([stats]))

        assert f'<td class="address">{expected}</td>' in result

    def test_unprintable_reference_id_falls_back_to_hex(self) -> None:
        """An addressless row with binary reference ID shows the hex ID."""
        stats = make_source_stats(address="", reference_id=0xC1A3CC71)

        result = str(stats_table([stats]))

        assert '<td class="address">C1A3CC71</td>' in result

    def test_network_address_is_preferred(self) -> None:
        """A source with an address keeps it, whatever the reference ID says."""
        stats = make_source_stats(address="192.168.1.1", reference_id=0x4E4D4541)

        result = str(stats_table([stats]))

        assert '<td class="address">192.168.1.1</td>' in result
