"""Unit tests for source statistics table component."""

import pytest
from pychrony import SourceStats
from pychrony.testing import make_source_stats

from second_hand.components.stats import stats_table
from second_hand.main import STATIC_DIR


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

    @pytest.mark.parametrize(
        ("std_dev", "expected"),
        [
            (6.75e-07, "675 ns"),
            (5.12e-04, "512.0 \u00b5s"),
            (0.0123, "12.300 ms"),
        ],
    )
    def test_std_dev_formatted_with_units(self, std_dev: float, expected: str) -> None:
        """Test standard deviation is scaled to a unit, not scientific notation."""
        result = str(stats_table([make_source_stats(std_dev=std_dev)]))

        assert f'<td class="std-dev">{expected}</td>' in result

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

        assert f'<span class="source-name">{expected}</span>' in result

    def test_unprintable_reference_id_falls_back_to_hex(self) -> None:
        """An addressless row with binary reference ID shows the hex ID."""
        stats = make_source_stats(address="", reference_id=0xC1A3CC71)

        result = str(stats_table([stats]))

        assert '<span class="source-name">C1A3CC71</span>' in result

    def test_network_address_is_preferred(self) -> None:
        """A source with an address keeps it, whatever the reference ID says."""
        stats = make_source_stats(address="192.168.1.1", reference_id=0x4E4D4541)

        result = str(stats_table([stats]))

        assert '<span class="source-name">192.168.1.1</span>' in result


class TestSourceNames:
    """Tests for showing resolved hostnames in the statistics table."""

    def test_resolved_source_shows_hostname_with_address_in_title(self) -> None:
        """A resolved source reads the same here as in the NTP sources table."""
        stats = make_source_stats(address="8.8.8.8")

        result = str(stats_table([stats], {"8.8.8.8": "dns.google"}))

        assert '<span class="source-name" title="8.8.8.8">dns.google</span>' in result

    def test_unresolved_source_shows_address_without_title(self) -> None:
        """No PTR record means no title, so no hover affordance either."""
        stats = make_source_stats(address="192.168.1.1")

        result = str(stats_table([stats], {"8.8.8.8": "dns.google"}))

        assert '<span class="source-name">192.168.1.1</span>' in result

    def test_rows_key_on_the_address_not_the_name(self) -> None:
        """dashboard.js links this row to the source's by data-address."""
        stats = make_source_stats(address="8.8.8.8")

        result = str(stats_table([stats], {"8.8.8.8": "dns.google"}))

        assert 'data-address="8.8.8.8"' in result
        assert 'data-address="dns.google"' not in result

    def test_refclock_row_keys_on_the_name_the_sources_table_uses(self) -> None:
        """chronyd gives a refclock no address here, but its sources row has one."""
        stats = make_source_stats(address="", reference_id=0x4E4D4541)

        assert 'data-address="NMEA"' in str(stats_table([stats]))


class TestLinkedRowHighlight:
    """Tests for highlighting a source's rows across tables."""

    def test_linked_row_class_is_styled(self) -> None:
        """The class dashboard.js puts on linked rows must exist in the stylesheet."""
        js = (STATIC_DIR / "js" / "dashboard.js").read_text()
        css = (STATIC_DIR / "css" / "style.css").read_text()

        assert "'row-linked'" in js
        assert "tr.row-linked" in css
