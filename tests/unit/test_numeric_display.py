"""Guard against floats reaching the dashboard in scientific notation."""

import dataclasses
import re
from typing import Any

import pytest
from pychrony.testing import (
    make_rtc_data,
    make_source,
    make_source_stats,
    make_tracking,
)

from second_hand.components.rtc import rtc_section
from second_hand.components.sources import sources_table
from second_hand.components.stats import stats_table
from second_hand.components.tracking import tracking_section
from second_hand.schemas import SourceOut
from second_hand.services.chrony import ChronyData, EnrichedSource

# The sign is what separates an exponent from a hex reference ID like 4E4D4541:
# Python always writes one.
SCIENTIFIC = re.compile(r"\d[eE][+-]\d")

# Python only switches to exponents at the extremes: str() below 1e-4 and from
# 1e16, so ordinary fixture values pass even with a bad formatter.
EXTREME_VALUES = [6.75e-07, 1e-12, 1e-30, 0.0, 1e20]


def _with_every_float(factory: Any, value: float) -> Any:
    """Build a model with every float field set, so new fields are covered too.

    ``ref_time`` is skipped: it renders as a date, and 1e20 is past any year
    datetime can represent.
    """
    fields = dataclasses.fields(factory())
    return factory(
        **{f.name: value for f in fields if f.type is float and f.name != "ref_time"}
    )


def _visible_text(html: str) -> list[str]:
    """Text between tags; attributes hold values for scripts, not people."""
    return re.findall(r">([^<]+)<", html)


@pytest.mark.parametrize("value", EXTREME_VALUES)
class TestNoScientificNotation:
    """Every displayed number is scaled to a unit, whatever its magnitude."""

    def test_tracking_section(self, value: float) -> None:
        data = ChronyData(
            tracking=_with_every_float(make_tracking, value),
            sources=[],
            source_stats=[],
            rtc=None,
            error=None,
        )

        text = _visible_text(str(tracking_section(data)))

        assert not [t for t in text if SCIENTIFIC.search(t)]

    def test_sources_table(self, value: float) -> None:
        source = _with_every_float(make_source, value)

        text = _visible_text(str(sources_table([source])))

        assert not [t for t in text if SCIENTIFIC.search(t)]

    def test_stats_table(self, value: float) -> None:
        stats = _with_every_float(make_source_stats, value)

        text = _visible_text(str(stats_table([stats])))

        assert not [t for t in text if SCIENTIFIC.search(t)]

    def test_rtc_section(self, value: float) -> None:
        rtc = _with_every_float(make_rtc_data, value)

        text = _visible_text(str(rtc_section(rtc)))

        assert not [t for t in text if SCIENTIFIC.search(t)]

    def test_api_display_strings(self, value: float) -> None:
        """The browser patches the sources table with these strings."""
        source = _with_every_float(make_source, value)

        out = SourceOut.from_enriched(EnrichedSource(source=source), now=0.0)

        assert not SCIENTIFIC.search(out.latest_meas_display)
        assert not SCIENTIFIC.search(out.latest_meas_err_display)


def test_pattern_catches_exponents_but_not_hex_ids() -> None:
    assert SCIENTIFIC.search("7.84e-07")
    assert SCIENTIFIC.search("1E+20")
    assert not SCIENTIFIC.search("4E4D4541")
