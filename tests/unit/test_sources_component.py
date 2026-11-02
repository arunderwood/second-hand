"""Unit tests for sources table component."""

import re

import pytest
from pychrony import Source, SourceState
from pychrony.testing import make_source

from second_hand.components.sources import sources_table
from second_hand.main import STATIC_DIR
from second_hand.presentation import SOURCE_STATE_CLASSES
from second_hand.services.chrony import EnrichedSource


@pytest.fixture
def mock_sources() -> list[Source]:
    """Create mock sources for testing using factory defaults."""
    return [
        make_source(
            address="192.168.1.1",
            poll=6,
            state=SourceState.SELECTED,
            reachability=255,
        ),
        make_source(
            address="10.0.0.1",
            poll=8,
            state=SourceState.UNSELECTED,
            reachability=0,
        ),
    ]


class TestSourcesTable:
    """Tests for sources_table component."""

    def test_sources_table_displays_all_sources(
        self, mock_sources: list[Source]
    ) -> None:
        """Test sources table displays all provided sources."""
        result = str(sources_table(mock_sources))

        for source in mock_sources:
            assert source.address in result

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


class TestRowAddressKey:
    def test_rows_carry_their_address(self, mock_sources: list[Source]) -> None:
        """dashboard.js matches API updates to rows by this attribute."""
        result = str(sources_table(mock_sources))
        assert 'data-address="192.168.1.1"' in result
        assert 'data-address="10.0.0.1"' in result

    def test_js_clears_every_state_class(self) -> None:
        """dashboard.js must know every class the server can put on a row."""
        js = (STATIC_DIR / "js" / "dashboard.js").read_text()
        block = re.search(r"SOURCE_STATE_CLASSES = \[(.*?)\]", js, re.DOTALL)
        assert block is not None
        assert tuple(re.findall(r"'([^']+)'", block.group(1))) == SOURCE_STATE_CLASSES


class TestEnrichedAddressCell:
    """The address cell when sources carry hostnames and country data."""

    @staticmethod
    def _cell(hostname: str | None, country_code: str | None = None) -> str:
        source = EnrichedSource(
            source=make_source(address="8.8.8.8"),
            country_code=country_code,
            hostname=hostname,
        )
        return str(sources_table([source]))

    def test_resolved_name_carries_the_address_as_its_title(self) -> None:
        """Hovering the name is how the address stays reachable."""
        assert (
            '<span class="source-name" title="8.8.8.8">dns.google</span>'
            in self._cell("dns.google")
        )

    def test_unresolved_cell_shows_the_address_without_a_title(self) -> None:
        """No title means no hover affordance, which the CSS keys off."""
        result = self._cell(None)

        assert '<span class="source-name">8.8.8.8</span>' in result
        assert "title=" not in result.split('class="source-name"')[1][:40]

    def test_row_keys_on_the_address_not_the_name(self) -> None:
        """dashboard.js reloads the page if data-address stops matching."""
        result = self._cell("dns.google")

        assert 'data-address="8.8.8.8"' in result
        assert 'data-address="dns.google"' not in result

    def test_flag_and_name_both_render(self) -> None:
        result = self._cell("dns.google", country_code="DE")

        assert 'class="country-flag"' in result
        assert 'class="source-name" title="8.8.8.8"' in result

    def test_name_is_escaped(self) -> None:
        """htpy escapes it, but the name is third-party data either way."""
        result = self._cell("a&b")

        assert "a&amp;b" in result
        assert "a&b" not in result

    def test_plain_source_still_renders_a_name_span(self) -> None:
        """dashboard.js looks for the span on every row, enriched or not."""
        result = str(sources_table([make_source(address="8.8.8.8")]))

        assert '<span class="source-name">8.8.8.8</span>' in result
