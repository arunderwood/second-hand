"""Base layout component for second-hand pages."""

from htpy import (
    Element,
    a,
    body,
    div,
    h1,
    head,
    html,
    link,
    meta,
    p,
    script,
    span,
    title,
)

from second_hand import __version__
from second_hand.components.tooltips import TooltipContent

__all__ = ["base_layout", "error_page", "source_name", "tooltip_label"]


def _versioned(url: str) -> str:
    """Tie an asset's URL to this release.

    A new URL reaches a browser still treating its old copy as fresh, which no
    response header can: that browser never asks.
    """
    return f"{url}?v={__version__}"


def source_name(address: str, hostname: str | None = None) -> Element:
    """Name a source in a table row, as dashboard.js expects to find it.

    Always rendered, even with no hostname, so dashboard.js only rewrites its
    text.

    Args:
        address: The source's address, or its label if it has none.
        hostname: Resolved hostname, shown with the address as its title.

    Returns:
        htpy Element holding the source's name.
    """
    return span(".source-name", title=address if hostname else None)[
        hostname or address
    ]


def tooltip_label(text: str, tooltip: TooltipContent, *, section: str) -> Element:
    """Create a label with accessible tooltip.

    Uses pure CSS tooltips with ARIA attributes for WCAG 2.1 AA compliance.
    The tooltip content is stored in a data attribute for CSS display,
    and in a hidden span for screen reader access.

    Args:
        text: The label text to display.
        tooltip: TooltipContent object with description and optional guidance.
        section: Dashboard section the label sits in. Several sections share
            label text ("Offset", "Stratum"), and the section keeps the
            ``aria-describedby`` target id unique on the page.

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
    slug = text.lower().replace(" ", "-").replace("/", "-")
    label_id = f"tip-{section}-{slug}"

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
    return html(lang="en")[
        head[
            meta(charset="utf-8"),
            meta(name="viewport", content="width=device-width, initial-scale=1"),
            title[page_title],
            link(rel="stylesheet", href=_versioned("/static/css/style.css")),
            link(rel="icon", href="/static/favicon.svg", type="image/svg+xml"),
        ],
        body[
            content,
            script(src=_versioned("/static/js/dashboard.js"), defer=True),
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
    content = div(".error-page")[
        div(".error-container")[
            h1(".error-code")[str(code)],
            p(".error-message")[message],
            a(".error-link", href="/")["Return to Dashboard"],
        ]
    ]
    return base_layout(f"Error {code} - second-hand", content)
