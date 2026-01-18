"""Base layout component for second-hand pages."""

from htpy import Element, body, head, html, link, meta, title


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
            link(rel="stylesheet", href="/static/css/style.css"),
        ],
        body[content],
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
