# Quickstart: Client Visibility

Validation scenarios proving the feature end to end. Contracts: `contracts/`; shapes:
`data-model.md`.

## Prerequisites

- `uv sync` (plus `--group browser` for layout tests)
- Docker for integration and .deb tests

## 1. Unit tests (no chronyd)

```bash
uv run pytest tests/unit tests/test_components.py
```

Expected: reader parser tests (clients/serverstats CSV fixtures per chrony 4.3/4.5/4.6/4.8),
monitoring-only exclusion, snapshot model validation, R3 decision-ladder tests (flag,
remote address, unit states, missing/stale/invalid snapshot), FR-021 address redaction,
and clients-panel component states (data / zero / unavailable / stale / absent) all pass.
chronyc and systemctl are mocked; nothing here touches a real chronyd.

## 2. Dev loop (no systemd)

```bash
# Terminal 1 — reader writing to a scratch path (needs a local chronyd; any state is fine)
SECOND_HAND_CLIENTS_SNAPSHOT_PATH=/tmp/sh-snapshot.json \
  uv run python -m second_hand.reader

# Terminal 2 — dashboard reading the same path
SECOND_HAND_CLIENTS_SNAPSHOT_PATH=/tmp/sh-snapshot.json \
  uv run uvicorn second_hand.main:app --reload
```

Expected: `curl localhost:8000/api/clients` returns `status: "ok"` (or an unavailable
reason that matches your chronyd's state); the dashboard shows the Clients panel.
Without the reader running, the panel shows the unavailable state and everything else
still works (FR-019).

## 3. Integration tests (real chronyd, SC-003)

```bash
docker compose -f docker/docker-compose.test.yml run --rm --build test-integration
```

Expected additions: a test generates client traffic, runs the reader's collection 10×
consecutively, and asserts `chronyc clients` / `chronyc serverstats` counters are
byte-identical before and after (SC-003, FR-011); snapshot content matches the traffic
generated; monitoring-only hosts are absent from `clients`.

## 4. Packaged behaviour (.deb matrix, FR-015/FR-016/SC-001/SC-002/SC-006)

```bash
# existing deb test entry point, now also covering the reader
./docker/test-deb.sh
```

Expected new checks, per distro image (Debian 12/13, Ubuntu 24.04/26.04):

1. **Out of the box**: both units active after install; dashboard shows a Clients panel
   with a client count after synthetic NTP traffic (SC-001).
2. **Handoff permissions** (R2 verification): inside the container, the web unit's user can
   read `/run/second-hand-reader/snapshot.json`, cannot write it, and other users cannot
   read it.
3. **Unit-state check** (R3 verification): a stopped-but-enabled reader renders as
   "reader not running" — the hardened web service classified the unit from its
   on-disk state.
4. **Off route a**: set `SECOND_HAND_CLIENTS_ENABLED=false` in `/etc/default/second-hand`,
   restart both; panel and `/api/clients` absent (404), reader inactive.
5. **Off route b**: `systemctl disable --now second-hand-reader`; same assertions (FR-016).
6. **Upgrade**: with the feature off, `UPGRADE_TO=` path still shows it off (SC-006).
7. **Security scores**: `second-hand.service` within its existing ceiling (SC-002);
   `second-hand-reader.service` within its new ceiling.
8. **Degradation**: stop chronyd → panel shows `chronyd_unreachable`; `noclientlog` →
   `client_logging_disabled`; dashboard stays 200 throughout (FR-017).

## 5. Layout tests

```bash
uv sync --group browser && uv run playwright install chromium && uv run pytest tests/browser
```

Expected: clients panel added to the layout suite — full IPv6 addresses stay in their
cells, the table caps rows and shows the "N more" line, no sideways scroll (spec edge
cases; SC-004's page-responsiveness half is asserted here with a 4,000-row fixture served
through the real app).

## 6. Manual sanity (SC-005)

On a packaged host serving real clients: open the dashboard, answer "how many devices used
this in the last hour?" from the last-seen buckets and "is device X still polling?" from
the table — both without a shell.
