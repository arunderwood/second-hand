"""Base layout component for second-hand pages."""

from htpy import Element, body, head, html, link, meta, span, title

from second_hand.components.tooltips import TooltipContent

__all__ = ["base_layout", "error_page", "tooltip_label"]


def tooltip_label(text: str, tooltip: TooltipContent) -> Element:
    """Create a label with accessible tooltip.

    Uses pure CSS tooltips with ARIA attributes for WCAG 2.1 AA compliance.
    The tooltip content is stored in a data attribute for CSS display,
    and in a hidden span for screen reader access.

    Args:
        text: The label text to display.
        tooltip: TooltipContent object with description and optional guidance.

    Returns:
        htpy Element with tooltip trigger and accessible content.
    """
    # Build tooltip text including good/bad value guidance if present
    tooltip_text = tooltip.description
    if tooltip.good_values:
        tooltip_text += f" Good: {tooltip.good_values}."
    if tooltip.bad_values:
        tooltip_text += f" Bad: {tooltip.bad_values}."

    # Generate unique ID for aria-describedby
    label_id = f"tip-{text.lower().replace(' ', '-').replace('/', '-')}"

    return span(
        ".tooltip-trigger",
        tabindex="0",
        role="button",
        aria_describedby=label_id,
        **{"data-tooltip": tooltip_text},
    )[
        text,
        span(id=label_id, role="tooltip", **{"class": "sr-only"})[tooltip_text],
    ]


def base_layout(page_title: str, content: Element) -> Element:
    """Create the base HTML layout for all pages.

    Args:
        page_title: The title to display in the browser tab.
        content: The main content element to render in the body.

    Returns:
        Complete HTML document as an htpy Element.
    """
    from htpy import script

    return html(lang="en")[
        head[
            meta(charset="utf-8"),
            meta(name="viewport", content="width=device-width, initial-scale=1"),
            title[page_title],
            link(rel="stylesheet", href="/static/css/style.css"),
            link(rel="icon", href="/static/favicon.svg", type="image/svg+xml"),
        ],
        body[
            content,
            script(src="/static/js/dashboard.js", defer=True),
        ],
    ]


def error_page(code: int, message: str) -> Element:
    """Create a styled error page.

    Args:
        code: HTTP error code (e.g., 404, 500).
        message: Human-readable error message.

    Returns:
        Complete HTML error page as an htpy Element.
    """
    from htpy import a, div, h1, p

    content = div(".error-page")[
        div(".error-container")[
            h1(".error-code")[str(code)],
            p(".error-message")[message],
            a(".error-link", href="/")["Return to Dashboard"],
        ]
    ]
    return base_layout(f"Error {code} - second-hand", content)
