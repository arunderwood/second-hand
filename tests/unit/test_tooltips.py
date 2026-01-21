"""Tests for tooltip content and the tooltip_label helper."""

import pytest

from second_hand.components.base import tooltip_label
from second_hand.components.tooltips import (
    RTC_TOOLTIPS,
    SOURCE_TOOLTIPS,
    STATS_TOOLTIPS,
    TRACKING_TOOLTIPS,
    TooltipContent,
)


class TestTooltipContent:
    """Tests for TooltipContent dataclass."""

    def test_tooltip_content_description_only(self) -> None:
        tooltip = TooltipContent(description="Test description")
        assert tooltip.description == "Test description"
        assert tooltip.good_values is None
        assert tooltip.bad_values is None

    def test_tooltip_content_with_good_values(self) -> None:
        tooltip = TooltipContent(description="Test", good_values="< 10")
        assert tooltip.good_values == "< 10"

    def test_tooltip_content_with_bad_values(self) -> None:
        tooltip = TooltipContent(description="Test", bad_values="> 100")
        assert tooltip.bad_values == "> 100"

    def test_tooltip_content_immutable(self) -> None:
        tooltip = TooltipContent(description="Test")
        with pytest.raises(AttributeError):
            tooltip.description = "Modified"  # type: ignore[misc]


class TestTooltipLabel:
    """Tests for tooltip_label helper function."""

    def test_tooltip_label_generates_html(self) -> None:
        tooltip = TooltipContent(description="Test description")
        result = str(tooltip_label("Test Label", tooltip))

        assert "Test Label" in result
        assert "tooltip-trigger" in result
        assert "data-tooltip" in result

    def test_tooltip_label_includes_description(self) -> None:
        tooltip = TooltipContent(description="Test description")
        result = str(tooltip_label("Test", tooltip))

        assert "Test description" in result

    def test_tooltip_label_includes_good_values(self) -> None:
        tooltip = TooltipContent(description="Desc", good_values="< 10 ms")
        result = str(tooltip_label("Test", tooltip))

        assert "Good: &lt; 10 ms" in result  # HTML escaped

    def test_tooltip_label_includes_bad_values(self) -> None:
        tooltip = TooltipContent(description="Desc", bad_values="> 100 ms")
        result = str(tooltip_label("Test", tooltip))

        assert "Bad: &gt; 100 ms" in result  # HTML escaped

    def test_tooltip_label_has_tabindex(self) -> None:
        tooltip = TooltipContent(description="Test")
        result = str(tooltip_label("Test", tooltip))

        assert 'tabindex="0"' in result

    def test_tooltip_label_has_role_button(self) -> None:
        tooltip = TooltipContent(description="Test")
        result = str(tooltip_label("Test", tooltip))

        assert 'role="button"' in result

    def test_tooltip_label_has_aria_describedby(self) -> None:
        tooltip = TooltipContent(description="Test")
        result = str(tooltip_label("Test Label", tooltip))

        assert "aria-describedby" in result
        assert "tip-test-label" in result  # Generated ID

    def test_tooltip_label_has_sr_only_content(self) -> None:
        tooltip = TooltipContent(description="Test description")
        result = str(tooltip_label("Test", tooltip))

        assert 'class="sr-only"' in result
        assert 'role="tooltip"' in result


class TestTrackingTooltips:
    """Tests for TRACKING_TOOLTIPS content."""

    def test_all_expected_keys_present(self) -> None:
        expected_keys = [
            "reference",
            "reference_ip",
            "stratum",
            "leap_status",
            "ref_time",
            "offset",
            "last_offset",
            "rms_offset",
            "frequency",
            "residual_freq",
            "skew",
            "root_delay",
            "root_dispersion",
            "update_interval",
        ]
        for key in expected_keys:
            assert key in TRACKING_TOOLTIPS, f"Missing key: {key}"

    def test_all_tooltips_have_descriptions(self) -> None:
        for key, tooltip in TRACKING_TOOLTIPS.items():
            assert tooltip.description, f"Empty description for {key}"
            assert len(tooltip.description) > 10, f"Short description for {key}"

    def test_stratum_has_good_bad_values(self) -> None:
        tooltip = TRACKING_TOOLTIPS["stratum"]
        assert tooltip.good_values is not None
        assert tooltip.bad_values is not None

    def test_offset_has_thresholds(self) -> None:
        tooltip = TRACKING_TOOLTIPS["offset"]
        assert tooltip.good_values is not None
        assert tooltip.bad_values is not None


class TestSourceTooltips:
    """Tests for SOURCE_TOOLTIPS content."""

    def test_all_expected_keys_present(self) -> None:
        expected_keys = [
            "mode",
            "state",
            "stratum",
            "poll",
            "reach",
            "last_rx",
            "latest_meas",
            "latest_meas_err",
        ]
        for key in expected_keys:
            assert key in SOURCE_TOOLTIPS, f"Missing key: {key}"

    def test_mode_describes_symbols(self) -> None:
        tooltip = SOURCE_TOOLTIPS["mode"]
        # Should describe ^, =, # symbols
        assert "^" in tooltip.description or "server" in tooltip.description.lower()

    def test_state_describes_symbols(self) -> None:
        tooltip = SOURCE_TOOLTIPS["state"]
        # Should describe *, +, -, ?, x, ~ symbols
        assert "*" in tooltip.description or "selected" in tooltip.description.lower()

    def test_reach_has_good_bad_values(self) -> None:
        tooltip = SOURCE_TOOLTIPS["reach"]
        assert tooltip.good_values is not None
        assert "377" in tooltip.good_values


class TestStatsTooltips:
    """Tests for STATS_TOOLTIPS content."""

    def test_all_expected_keys_present(self) -> None:
        expected_keys = [
            "samples",
            "runs",
            "span",
            "std_dev",
            "resid_freq",
            "skew",
            "offset",
            "offset_err",
            "reference_id",
        ]
        for key in expected_keys:
            assert key in STATS_TOOLTIPS, f"Missing key: {key}"

    def test_std_dev_has_good_bad_values(self) -> None:
        tooltip = STATS_TOOLTIPS["std_dev"]
        assert tooltip.good_values is not None
        assert tooltip.bad_values is not None


class TestRtcTooltips:
    """Tests for RTC_TOOLTIPS content."""

    def test_all_expected_keys_present(self) -> None:
        expected_keys = [
            "ref_time",
            "samples",
            "runs",
            "span",
            "offset",
            "drift_rate",
        ]
        for key in expected_keys:
            assert key in RTC_TOOLTIPS, f"Missing key: {key}"

    def test_all_tooltips_have_descriptions(self) -> None:
        for key, tooltip in RTC_TOOLTIPS.items():
            assert tooltip.description, f"Empty description for {key}"
