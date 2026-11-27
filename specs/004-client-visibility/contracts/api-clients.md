# Contract: GET /api/clients

JSON feed for the Clients panel, following the `/api/sources` conventions (same refresh
cycle, same error envelope `ApiError`).

## Responses

| Condition (R3 ladder) | Status | Body |
|---|---|---|
| Feature off (FR-016, either route) | 404 | FastAPI default not-found — the route answers as if it did not exist; no hint that client data was ever here |
| Remote chronyd (FR-020) | 404 | same |
| Reader not installed / not running / snapshot invalid | 200 | `ClientsResponse` with `status="unavailable"`, `reason`, `reason_detail` |
| Reader-reported unavailability (too old, logging off, unreachable) | 200 | same shape, reader's reason passed through |
| Data present | 200 | `ClientsResponse` with `status="ok"` |

Unavailable is 200, not 5xx: the dashboard JS treats it as content (FR-017 "the rest of the
dashboard keeps working"), and only transport failures are errors.

## ClientsResponse (status="ok")

```json
{
  "status": "ok",
  "reason": null,
  "reason_detail": null,
  "taken_at": 1795900000,
  "age_seconds": 7,
  "stale": false,
  "summary": { "...": "ClientSummary, see data-model.md" },
  "totals": { "...": "ServerTotals" },
  "table_enabled": true,
  "clients": [ { "...": "ClientRecord" } ],
  "clients_truncated": 3,
  "refresh_interval": 30
}
```

Rules:
- `stale` is true when `age_seconds > 3 × interval` (FR-018); the panel must show
  `age_seconds` always, and a stale marking when `stale`.
- When the per-client table setting is off (FR-021): `table_enabled=false`,
  `clients=[]`, `clients_truncated=0` — no client address leaves the server. Aggregates
  and totals still fill.
- `clients` is ordered most-recently-seen first and already capped by the reader;
  `clients_truncated` says how many more exist (FR-006).
- `reason` enum adds two dashboard-side values to the reader's set:
  `reader_not_installed`, `reader_not_running`.

## Dashboard page

The server-rendered panel (htpy component `components/clients.py`) renders from the same
`ClientsResponse` build, so page and API cannot drift:
- Absent conditions render nothing at all — no placeholder element (FR-016, FR-020).
- The zero-clients state shows the "chronyd only serves clients its configuration allows"
  hint (spec edge case), distinct from unavailable.
- `log_records_dropped > 0` renders the rolling-window/log-full indicator (FR-007).
- IPv6 addresses render untruncated (layout test covers this).
