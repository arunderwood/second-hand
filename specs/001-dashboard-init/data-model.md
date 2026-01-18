# Data Model: Dashboard Initialization

**Feature**: 001-dashboard-init
**Date**: 2026-01-17

## Overview

This phase establishes the project foundation with a static dashboard page. There is no persistent data storage - all entities are configuration or runtime objects.

## Entities

### Settings

Configuration for the application runtime behavior.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| debug | bool | No | false | Enable debug mode with verbose logging |
| host | str | No | "127.0.0.1" | Server bind address |
| port | int | No | 8000 | Server bind port |

**Source**: Environment variables with `SECOND_HAND_` prefix
**Validation**: Port must be 1-65535; host must be valid IP or hostname

### DashboardContext

Template context passed to the dashboard page.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| request | Request | Yes | FastAPI request object (required by Jinja2) |
| title | str | Yes | Page title ("second-hand Dashboard") |
| version | str | Yes | Application version from package metadata |
| placeholder_message | str | Yes | Message indicating future chrony stats location |

**Lifecycle**: Created fresh on each request; no state persistence

## Relationships

```text
Settings (singleton)
    └── configures → FastAPI Application
                         └── renders → DashboardContext
                                           └── populates → dashboard.html
```

## State Transitions

N/A - No stateful entities in this phase. The dashboard is purely request/response.

## Future Considerations

When chrony integration is added (future feature), new entities will include:
- `ChronySource`: NTP source information
- `ChronyTracking`: System clock tracking data
- `ChronyStats`: Server statistics

These are explicitly out of scope for 001-dashboard-init.

## Validation Rules

| Entity | Rule | Error Behavior |
|--------|------|----------------|
| Settings.port | 1 <= port <= 65535 | Startup failure with clear message |
| Settings.host | Valid IP or "localhost" | Startup failure with clear message |

## Data Volume

- Settings: 1 instance (singleton)
- DashboardContext: 1 per request (ephemeral, ~100 bytes)
- No database, no file storage, no caching required
