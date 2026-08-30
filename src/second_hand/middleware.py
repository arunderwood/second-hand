"""Security response headers middleware.

Adds standard defense-in-depth response headers to responses from the
routes, mounted ``StaticFiles``, and handled exceptions. Implemented as a
pure ASGI middleware rather than ``BaseHTTPMiddleware`` to avoid buffering
responses.

Starlette always places ``ServerErrorMiddleware`` outside the user
middleware stack, so unhandled-exception responses bypass this middleware
entirely. ``second_hand.main`` covers that case with a 500 handler built
from :func:`build_security_headers`.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

__all__ = [
    "CONTENT_SECURITY_POLICY",
    "DOCS_CONTENT_SECURITY_POLICY",
    "SecurityHeadersMiddleware",
    "build_security_headers",
]

# style.css imports Google Fonts, which in turn loads font files from
# fonts.gstatic.com. Both hosts must be allowed or the dashboard silently
# falls back to system fonts.
_GOOGLE_FONTS_CSS = "https://fonts.googleapis.com"
_GOOGLE_FONTS_FILES = "https://fonts.gstatic.com"

# Deny-by-default policy, widened only where the dashboard actually needs it:
# an external stylesheet, an external script, same-origin images, and a
# same-origin fetch() to /api/sources.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'none'",
        "script-src 'self'",
        f"style-src 'self' {_GOOGLE_FONTS_CSS}",
        f"font-src {_GOOGLE_FONTS_FILES}",
        "img-src 'self'",
        "connect-src 'self'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ]
)

# Swagger UI and ReDoc are loaded from a CDN and inject both inline scripts
# and runtime-generated <style> elements, so they cannot run under the policy
# above. This relaxed policy is applied to the documentation paths only, and
# only in dev mode -- the docs routes do not exist in production.
_SWAGGER_CDN = "https://cdn.jsdelivr.net"
_FASTAPI_ASSETS = "https://fastapi.tiangolo.com"

DOCS_CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'none'",
        f"script-src 'self' 'unsafe-inline' {_SWAGGER_CDN}",
        f"style-src 'self' 'unsafe-inline' {_SWAGGER_CDN} {_GOOGLE_FONTS_CSS}",
        f"font-src {_GOOGLE_FONTS_FILES} {_SWAGGER_CDN} data:",
        # cdn.redoc.ly is deliberately omitted: it serves only ReDoc's own
        # footer branding logo, so blocking it costs a cosmetic image and one
        # console warning on /redoc.
        f"img-src 'self' {_FASTAPI_ASSETS} data:",
        "connect-src 'self'",
        "worker-src 'self' blob:",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ]
)

_BASE_HEADERS: dict[str, str] = {
    "content-security-policy": CONTENT_SECURITY_POLICY,
    "x-content-type-options": "nosniff",
    # Redundant with frame-ancestors for modern browsers, kept for older ones.
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}


def build_security_headers(
    *,
    hsts_max_age: int = 0,
    hsts_include_subdomains: bool = True,
) -> dict[str, str]:
    """Build the full set of security response headers.

    Shared by the middleware and by the 500 handler, which Starlette invokes
    from outside the user middleware stack.

    Args:
        hsts_max_age: ``Strict-Transport-Security`` max-age in seconds.
            ``0`` omits the header entirely, which is correct over plain HTTP.
        hsts_include_subdomains: Append ``includeSubDomains`` when HSTS is
            enabled.

    Returns:
        Mapping of lowercase header name to value.
    """
    headers = dict(_BASE_HEADERS)

    if hsts_max_age > 0:
        hsts = f"max-age={hsts_max_age}"
        if hsts_include_subdomains:
            hsts += "; includeSubDomains"
        headers["strict-transport-security"] = hsts

    return headers


class SecurityHeadersMiddleware:
    """Attach security response headers to every HTTP response.

    Values are overwritten rather than merged: a security header must not be
    silently weakened by whatever produced the response.

    Args:
        app: The wrapped ASGI application.
        hsts_max_age: ``Strict-Transport-Security`` max-age in seconds.
            ``0`` (the default) omits the header entirely, which is correct
            when the app is served over plain HTTP.
        hsts_include_subdomains: Append ``includeSubDomains`` when HSTS is
            enabled.
        docs_paths: Exact request paths that receive
            :data:`DOCS_CONTENT_SECURITY_POLICY` instead of the strict policy.
            Empty by default; ``second_hand.main`` populates it only in dev
            mode, where the API documentation routes are mounted.
    """

    def __init__(
        self,
        app: ASGIApp,
        /,
        *,
        hsts_max_age: int = 0,
        hsts_include_subdomains: bool = True,
        docs_paths: frozenset[str] = frozenset(),
    ) -> None:
        self.app = app
        self.headers = build_security_headers(
            hsts_max_age=hsts_max_age,
            hsts_include_subdomains=hsts_include_subdomains,
        )
        self.docs_paths = docs_paths
        self.docs_headers = dict(self.headers)
        self.docs_headers["content-security-policy"] = DOCS_CONTENT_SECURITY_POLICY

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Wrap the response start message to inject security headers."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        active = (
            self.docs_headers if scope.get("path") in self.docs_paths else self.headers
        )

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in active.items():
                    headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)
