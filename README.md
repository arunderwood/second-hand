<div align="center">
  <img src="src/second_hand/static/img/logo.svg" width="100" height="100" alt="second-hand">
  <h1>second-hand</h1>
  <p><strong>A modern, type-safe dashboard for monitoring chrony time synchronization statistics.</strong></p>
</div>
<img width="1710" height="957" alt="image" src="https://github.com/user-attachments/assets/7d90ee0e-7a63-4bab-ab22-5e800ee0c82c" />
<br>
<br>

Second-hand provides a clean, responsive web interface for viewing NTP/chrony time statistics on your homelab or server. Built with Python 3.14, FastAPI, and htpy for type-safe HTML generation.

**Current Status**: Dashboard initialization phase - displays placeholder content awaiting chrony integration.

## Quick Start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/arunderwood/second-hand.git
cd second-hand
uv sync --all-extras
uv run uvicorn second_hand.main:app --reload
```

Open http://localhost:8000

## Development

### Project Structure

```text
src/second_hand/
├── main.py          # FastAPI application
├── config.py        # Configuration management
└── components/      # htpy HTML components (type-safe!)
    ├── base.py      # Base layout
    └── dashboard.py # Dashboard page
src/static/css/      # Stylesheets
tests/               # Test suite
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=second_hand --cov-report=term-missing
```

### Type Checking

```bash
uv run ty check src/
```

### Linting

```bash
uv run ruff check .
uv run ruff format .
```

### Configuration

All settings are optional with sensible defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECOND_HAND_DEBUG` | `false` | Dev mode: auto-reload plus `/docs` and `/redoc` |
| `SECOND_HAND_HOST` | `127.0.0.1` | Server bind address |
| `SECOND_HAND_PORT` | `8000` | Server bind port |
| `SECOND_HAND_HSTS_MAX_AGE` | `0` | HSTS `max-age` in seconds; `0` disables the header. Only set this when serving over HTTPS |
| `SECOND_HAND_HSTS_INCLUDE_SUBDOMAINS` | `true` | Append `includeSubDomains` when HSTS is enabled |

### Security Headers

Every response carries a strict `Content-Security-Policy` (`default-src 'none'`, no
`unsafe-inline`), plus `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and
`Referrer-Policy: no-referrer`.

`Strict-Transport-Security` is off by default because the app ships as a plain-HTTP
service. Enable it via `SECOND_HAND_HSTS_MAX_AGE` once TLS is terminated in front of it.

The CSP allows `fonts.googleapis.com` and `fonts.gstatic.com` because `style.css`
imports Google Fonts. Remove those directives if the fonts are ever vendored locally.

If you put a reverse proxy in front of this service, do **not** also set these headers
there. nginx's `add_header` appends rather than replaces, and a browser given two
`Content-Security-Policy` headers enforces the intersection of both — which silently
breaks the page. Either leave the app to set them, or use `proxy_hide_header` first.

### Dev Mode

`SECOND_HAND_DEBUG=true` enables uvicorn auto-reload and the interactive API
documentation at `/docs` and `/redoc`. Those routes do not exist otherwise: they are
unauthenticated attack surface, and the Debian package binds `0.0.0.0`.

Swagger UI and ReDoc load from a CDN and use inline scripts, so they cannot run under
the strict policy. In dev mode only, the documentation paths get a relaxed CSP; the
dashboard and API keep the strict one either way.

## Technology Stack

- **Python 3.14** - Latest Python with performance improvements
- **FastAPI** - Modern async web framework
- **htpy** - Type-safe HTML generation
- **uvicorn** - Lightning-fast ASGI server
- **ty** - Fast type checker from Astral
- **ruff** - Fast linter and formatter from Astral

## License

MIT
