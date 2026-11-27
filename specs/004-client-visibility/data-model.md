# Data Model: Client Visibility

**Branch**: `004-client-visibility` | **Date**: 2026-11-26

All models are pydantic `BaseModel`s in a module both processes import
(`second_hand/clients_model.py`). The reader serializes a `ReaderSnapshot` to the snapshot
file; the dashboard deserializes and validates it (untrusted-input discipline applies even
to a local file: a malformed snapshot must degrade to the unavailable state, never a 500).

## ClientRecord

One host from `chronyc -c -k clients` that qualifies as a client (NTP hits > 0 or
NTS-KE hits > 0). Monitoring-only rows are dropped before this model is built.

| Field | Type | Source (CSV position) | Notes |
|---|---|---|---|
| `address` | str | 1 | IPv4/IPv6 literal, validated as an address; shown as-is (FR-009) |
| `ntp_hits` | int ≥ 0 | 2 | |
| `ntp_drops` | int ≥ 0 | 3 | rate-limited/dropped requests |
| `ntp_interval` | int | 4 | log2 seconds, -1 = unknown (chrony convention) |
| `ntp_interval_limited` | int | 5 | interval after rate limiting, -1 = none |
| `last_ntp_seconds` | int ≥ 0 \| None | 6 | seconds since last NTP request |
| `nts_ke_hits` | int ≥ 0 | 7 | |
| `nts_ke_drops` | int ≥ 0 | 8 | |
| `last_nts_ke_seconds` | int ≥ 0 \| None | 10 | |
| `is_nts` | bool | derived | `nts_ke_hits > 0` |
| `last_seen_seconds` | int ≥ 0 | derived | min of last NTP / last NTS-KE ages |

Validation: a row that cannot be parsed into this shape poisons the whole snapshot to
`status=unavailable, reason=parse_error` — no partial publishes (R6).

## ClientSummary

Aggregates over **all** qualifying records (not just the published top-N).

| Field | Type | Notes |
|---|---|---|
| `total_clients` | int ≥ 0 | FR-001 |
| `nts_clients` | int ≥ 0 | FR-001 split |
| `ntp_clients` | int ≥ 0 | `total - nts` |
| `rate_limited_clients` | int ≥ 0 | records with `ntp_drops > 0` (FR-003) |
| `total_dropped_requests` | int ≥ 0 | sum of `ntp_drops` (FR-003) |
| `last_seen_buckets` | dict[str, int] | keys `1m`, `1h`, `1d`, `older` (FR-002) |
| `poll_interval_buckets` | dict[str, int] | keys `≤64s`, `≤1024s`, `>1024s`, `unknown` (FR-002) |

Bucket keys are a fixed enum in the model, so the panel and the API never disagree on them.

## ServerTotals

From `chronyc -c serverstats`, positional (R6). All counters are since chronyd started;
they reset when chronyd restarts, which the panel shows as-is (edge case in spec).

| Field | Type |
|---|---|
| `ntp_received` / `ntp_dropped` | int ≥ 0 |
| `cmd_received` / `cmd_dropped` | int ≥ 0 (monitoring requests) |
| `log_records_dropped` | int ≥ 0 (drives the "log is full / rolling window" indicator, FR-007) |
| `nts_ke_accepted` / `nts_ke_dropped` | int ≥ 0 |
| `ntp_authenticated` | int ≥ 0 |
| `ntp_interleaved` | int ≥ 0 |

## ReaderSnapshot

The document the reader publishes each cycle — the entire local-channel contract
(see `contracts/reader-snapshot.md` for the wire form).

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int, literal 1 | dashboard rejects unknown majors → unavailable state |
| `taken_at` | int (epoch s) | staleness is computed against this (FR-018) |
| `interval` | int (s) | the reader's cycle; staleness threshold = 3 × interval |
| `status` | `"ok"` \| `"unavailable"` | |
| `reason` | enum \| None | required when unavailable: `chrony_too_old`, `client_logging_disabled`, `chronyd_unreachable`, `permission_denied`, `parse_error` |
| `reason_detail` | str \| None | one short line for the panel (FR-017) |
| `summary` | ClientSummary \| None | present when ok |
| `totals` | ServerTotals \| None | present when ok |
| `clients` | list[ClientRecord] | top `max_rows` by `last_seen_seconds` ascending; `[]` when unavailable |
| `clients_truncated` | int ≥ 0 | how many qualifying clients exist beyond `clients` (FR-006) |

State transitions: there are none to persist — each cycle fully replaces the snapshot.
"Counters went down" and "chronyd restarted" need no special handling because the snapshot
is a pure point-in-time copy of chronyd's own state.

## Dashboard-side view models (not persisted)

`ClientsResponse` (the `/api/clients` body, `contracts/api-clients.md`) wraps the snapshot
with what only the dashboard knows:

| Field | Notes |
|---|---|
| `age_seconds`, `stale` | computed from `taken_at` at request time (FR-018) |
| `clients`, `clients_truncated` | omitted/empty when the per-client table setting is off (FR-021) |
| `table_enabled` | so the JS refresh renders the same shape the server did |
| `refresh_interval` | same contract as `SourcesResponse` |

Availability states the dashboard adds (R3 ladder): `reader_not_installed`,
`reader_not_running` — same rendering path as the reader-reported reasons.

## Settings (config.py additions)

| Setting (env) | Default | Constraint |
|---|---|---|
| `clients_enabled` (`SECOND_HAND_CLIENTS_ENABLED`) | `True` | FR-016 |
| `clients_table` (`SECOND_HAND_CLIENTS_TABLE`) | `True` | FR-021 |
| `clients_max_rows` (`SECOND_HAND_CLIENTS_MAX_ROWS`) | `100` | 1–10000 (spec assumption) |
| `clients_snapshot_path` (`SECOND_HAND_CLIENTS_SNAPSHOT_PATH`) | `/run/second-hand-reader/snapshot.json` | dev installs point it elsewhere |
| `reader_interval` (`SECOND_HAND_READER_INTERVAL`) | `30` | ≥ 10 (FR-013; reader-only) |

The reader reads the same `Settings` class, using only the last three plus
`clients_enabled` — one source of truth for defaults and validation.
