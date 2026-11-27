# Tasks: Client Visibility

**Input**: Design documents from `/specs/004-client-visibility/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — the spec demands them (SC-003's counter-invariance integration test,
SC-002's score ceilings) and the project's testing guidelines require mocked unit tests
plus dockerized integration tests.

**Organization**: Tasks are grouped by user story so each story is an independently
testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 (aggregates panel), US2 (per-client table), US3 (off switches)

## Phase 1: Setup

**Purpose**: Configuration surface every other task reads.

- [ ] T001 Add client settings to `src/second_hand/config.py` per data-model.md "Settings":
      `clients_enabled` (default True), `clients_table` (default True),
      `clients_max_rows` (`Settings.clients_max_rows`: 1–10000, default 100),
      `clients_snapshot_path` (default `/run/second-hand-reader/snapshot.json`),
      `reader_interval` (`Settings.reader_interval`: ≥ 10, default 30)
- [ ] T002 [P] Add validation tests for the new settings to `tests/test_config.py`
      (bounds rejection, env-prefix round-trip, defaults)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The reader, the snapshot channel, the dashboard-side availability ladder, and
the packaging that carries them. No story renders anything until data can exist.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 Create shared models in `src/second_hand/clients_model.py` per data-model.md:
      `ClientRecord` (`ClientRecord.address` validated as an IP literal; all hit/drop
      counts ≥ 0; `ClientRecord.is_nts` and `ClientRecord.last_seen_seconds` derived),
      `ClientSummary` (`ClientSummary.last_seen_buckets` and
      `ClientSummary.poll_interval_buckets` with fixed enum keys), `ServerTotals`
      (all counters ≥ 0), `ReaderSnapshot` (`ReaderSnapshot.schema_version` literal 1;
      `ReaderSnapshot.reason` enum, required when status is unavailable)
- [ ] T004 [P] Model validation tests in `tests/unit/test_clients_model.py`: unknown
      schema_version rejected, negative counts rejected, unavailable-without-reason
      rejected, unknown JSON fields ignored (contracts/reader-snapshot.md compatibility)
- [ ] T005 Implement collection in `src/second_hand/reader/collect.py` per
      contracts/reader-service.md: constant argv `chronyc -c -k clients` and
      `chronyc -c serverstats` (no shell, 10 s timeout, never `-r`), positional CSV
      parsing with minimum field count (research R6), monitoring-only exclusion
      (ntp_hits == 0 and nts_ke_hits == 0), incremental aggregation with bounded
      top-`clients_max_rows` recency heap (research R7), failure → reason mapping
      (`permission_denied`, `chronyd_unreachable`, `chrony_too_old`,
      `client_logging_disabled`, `parse_error`)
- [ ] T006 [P] Collection tests in `tests/unit/test_reader_collect.py` with CSV fixtures
      for chrony 4.3 / 4.5 / 4.6.1 / 4.8 (serverstats field growth), exclusion rule,
      truncation counting, and whole-snapshot `parse_error` poisoning on any bad row
      (data-model.md ClientRecord validation rule)
- [ ] T007 Implement atomic publisher in `src/second_hand/reader/publish.py` per
      contracts/reader-snapshot.md: write `snapshot.json.tmp`, fsync, rename
- [ ] T008 Implement reader entry point in `src/second_hand/reader/__init__.py` and
      `src/second_hand/reader/__main__.py`: fixed-interval loop (FR-013), exit 0
      immediately when `clients_enabled` is false (FR-016a), structured logging,
      runnable via `python -m second_hand.reader` and `PEX_MODULE=second_hand.reader`
- [ ] T009 [P] Publisher/entry tests in `tests/unit/test_reader_publish.py`: readers see
      whole documents during concurrent rewrites, disabled flag exits 0 before any
      chronyc call
- [ ] T010 Implement dashboard-side service in `src/second_hand/services/clients.py`:
      the research R3 availability ladder — flag check, loopback/Unix-socket address
      check (FR-020), `systemctl show second-hand-reader.service` with constant argv,
      snapshot load + pydantic validation (invalid ⇒ unavailable, never 500), staleness
      when age > 3 × `ReaderSnapshot.interval` against `ReaderSnapshot.taken_at`
      (data-model.md, FR-018)
- [ ] T011 [P] Ladder tests in `tests/unit/test_clients_service.py` with systemctl and
      filesystem mocked: every ladder rung — flag off, remote address, unit absent,
      unit disabled/masked, fresh, stale, missing, malformed snapshot
- [ ] T012 Create `debian/second-hand-reader.service` per the unit table in
      contracts/reader-service.md (User=_chrony, Group=second-hand-data,
      RuntimeDirectory mode 0750, UMask 0027, EnvironmentFile, PEX_MODULE, hardening
      block, AF_UNIX only, IPAddressDeny=any)
- [ ] T013 [P] Create `debian/second-hand.default` conffile (documented, commented-out
      `SECOND_HAND_CLIENTS_ENABLED` / `SECOND_HAND_CLIENTS_TABLE` /
      `SECOND_HAND_CLIENTS_MAX_ROWS`)
- [ ] T014 Wire packaging: `debian/postinst` creates system group `second-hand-data`
      if absent; `debian/second-hand.service` gains only `SupplementaryGroups=` and
      `EnvironmentFile=` (SC-002 — nothing else changes); install the new unit and
      default file via `debian/rules`; mention the reader in `debian/control`
- [ ] T015 Verify the two untested assumptions in the docker-systemd images on all four
      distros (research R2/R3): the DynamicUser web unit reads the snapshot via the
      supplementary group and cannot write it, and `systemctl show` works inside the
      hardened web unit; on failure, apply the documented fallbacks (R2: file 0644;
      R3: packaged marker file) and update research.md and contracts accordingly

**Checkpoint**: Reader produces real snapshots on a packaged host; dashboard service can
classify every state. Stories can start.

---

## Phase 3: User Story 1 — See whether my server is serving anyone (Priority: P1) 🎯 MVP

**Goal**: Clients panel with aggregates (count, NTS/NTP split, last-seen and poll-interval
buckets, rate-limited counts) and server-wide totals, fresh on the normal refresh cycle,
with honest unavailable/stale/zero states — out of the box on all four distros.

**Independent Test**: Install the .deb on a host whose chronyd serves at least one other
machine, generate NTP traffic, open the dashboard: non-zero client count and matching
totals with no setup (spec US1; quickstart §4.1).

### Implementation for User Story 1

- [ ] T016 [US1] Add `ClientsResponse` to `src/second_hand/schemas.py` per
      contracts/api-clients.md: status/reason (reader's enum plus
      `reader_not_installed` / `reader_not_running`), `taken_at`, `age_seconds`,
      `stale`, `summary`, `totals`, `refresh_interval`; table fields present but empty
      until US2
- [ ] T017 [P] [US1] Create the Clients panel in `src/second_hand/components/clients.py`:
      aggregates and totals display, bucket bars readable at a glance (FR-002),
      unavailable state with reason line (FR-017), stale marking with age (FR-018),
      zero-clients state with the allow-configuration hint (spec edge case), rolling-window
      indicator when `ServerTotals.log_records_dropped` > 0 (FR-007, data-model.md)
- [ ] T018 [US1] Add `GET /api/clients` to `src/second_hand/main.py` per
      contracts/api-clients.md: 404 when off (FR-016) or remote (FR-020), 200 with
      unavailable body otherwise, 200 ok with data
- [ ] T019 [US1] Wire the panel into `src/second_hand/components/dashboard.py` (absent —
      no placeholder — when off/remote) and add the clients fetch to
      `src/second_hand/static/js/dashboard.js` on the existing refresh cycle (FR-008)
- [ ] T020 [P] [US1] Endpoint tests in `tests/unit/test_api_clients.py`: all three
      response classes, 404 routes, reader-reason passthrough, stale computation
- [ ] T021 [P] [US1] Panel state tests in `tests/unit/test_clients_component.py`:
      data / zero / unavailable / stale / log-full renderings
- [ ] T022 [US1] Integration test in `tests/integration/test_clients_integration.py`
      against real chronyd (quickstart §3): generate client traffic, run collection 10×,
      assert `chronyc clients` and `chronyc serverstats` output byte-identical before and
      after (SC-003, FR-011); snapshot reflects the traffic; the test host's own
      monitoring connection is absent from records
- [ ] T023 [US1] Extend `docker/test-deb.sh`: reader unit active after install, panel
      shows a client count after synthetic traffic (SC-001), snapshot permission checks
      from T015 kept as regression assertions, second `systemd-analyze security` ceiling
      for `second-hand-reader.service`, existing web ceiling untouched (SC-002),
      degradation checks (stop chronyd → `chronyd_unreachable`; `noclientlog` →
      `client_logging_disabled`; page stays 200, FR-017)
- [ ] T024 [P] [US1] Layout test for the aggregates panel in `tests/browser` (values stay
      in boxes, no sideways scroll)

**Checkpoint**: US1 fully functional and independently testable — the MVP.

---

## Phase 4: User Story 2 — Identify which devices are using it (Priority: P2)

**Goal**: Per-client table beneath the aggregates: address, requests, drops, poll
interval, last-seen, NTS-KE — capped, recency-ordered, honest about truncation.

**Independent Test**: Two known devices polling: both addresses appear with plausible
last-seen/interval; stop one and its last-seen age grows on later refreshes (spec US2).

### Implementation for User Story 2

- [ ] T025 [US2] Populate the table fields of `ClientsResponse` in
      `src/second_hand/schemas.py` and `src/second_hand/services/clients.py`:
      `table_enabled`, `clients` (recency-ordered, already reader-capped),
      `clients_truncated`, gated by `Settings.clients_table` so no address leaves the
      server when off (FR-021, contracts/api-clients.md)
- [ ] T026 [US2] Add the per-client table to `src/second_hand/components/clients.py`:
      columns per FR-005 (NTS-KE shown where present), most-recent-first, row cap with
      "N more clients" line from `ReaderSnapshot.clients_truncated` (FR-006,
      data-model.md), and the matching rows in `static/js/dashboard.js` refresh
- [ ] T027 [P] [US2] Redaction and truncation tests in `tests/unit/test_api_clients.py`:
      `clients_table=false` ⇒ no address anywhere in page or API while aggregates remain
      (FR-021); truncation count correctness
- [ ] T028 [P] [US2] Layout tests in `tests/browser`: full IPv6 addresses stay in their
      cells (spec edge case), capped table with more-line, and a 4,000-client fixture
      served through the real app loads under 2 s (SC-004)

**Checkpoint**: US1 and US2 both work; table can be hidden independently of aggregates.

---

## Phase 5: User Story 3 — Turn client data off (Priority: P3)

**Goal**: Both off routes work, produce identical absence, stop the reader, and survive
upgrades.

**Independent Test**: Turn the feature off by the setting, then by `systemctl disable
--now second-hand-reader`; each time the panel and endpoints show nothing and the reader
is not running; upgrade the package and it stays off (spec US3; quickstart §4.4–4.6).

### Implementation for User Story 3

- [ ] T029 [US3] Off-state unit tests: `clients_enabled=false` ⇒ no panel markup in the
      dashboard HTML and `/api/clients` 404 (extend
      `tests/unit/test_clients_service.py` / `tests/unit/test_api_clients.py`);
      disabled/masked unit state ⇒ absent, enabled-but-stopped ⇒ unavailable
      (research R3 rungs 4 vs 7)
- [ ] T030 [US3] Extend `docker/test-deb.sh` with both off routes (quickstart §4.4–4.6):
      route a — set `SECOND_HAND_CLIENTS_ENABLED=false` in `/etc/default/second-hand`,
      restart both units, assert panel and endpoint absent and reader inactive;
      route b — `systemctl disable --now second-hand-reader`, same assertions (FR-016);
      then `UPGRADE_TO=` upgrade with the feature off and assert it stays off (SC-006)

**Checkpoint**: All three stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T031 [P] Operator documentation in `README.md`: the Clients panel, both off
      switches, the table-only switch, `/etc/default/second-hand`,
      `SECOND_HAND_CLIENTS_SNAPSHOT_PATH` and `SECOND_HAND_READER_INTERVAL` (constitution:
      every configuration option documented), and the data caveats
      (rolling log, counts can fall, chronyd restarts reset totals)
- [ ] T032 [P] Add memory assertions to `docker/test-deb.sh`
      (`systemctl show -p MemoryCurrent second-hand.service` under 100 MB with the
      feature active — SC-004's other half; `second-hand-reader.service` under its own
      small ceiling, so the plan's combined-footprint claim is measured, not assumed)
- [ ] T033 Run the full quickstart.md validation (unit, dev loop, integration, deb
      matrix, layout) plus the pre-commit checks (`ruff format`, `ruff check`,
      `ty check src/`, `pytest`), and reconcile any drift between the artifacts and
      what shipped

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: needs Phase 1 (T001). Blocks all stories. T015 (the
  R2/R3 verification) gates the packaging design — run it as soon as T012–T014 exist.
- **US1 (Phase 3)**: needs Phase 2. No dependency on US2/US3.
- **US2 (Phase 4)**: needs Phase 2; builds on US1's panel file (T017) and endpoint
  (T018), so it starts after US1's implementation tasks, though its tests are
  independent.
- **US3 (Phase 5)**: needs Phase 2; exercises behavior built in T008/T010/T018, so it
  can run in parallel with US2 once US1 is done.
- **Polish (Phase 6)**: after the stories you intend to ship.

### Within-phase ordering

- T003 → T005/T007 → T008 (models before collector/publisher before entry)
- T010 needs T003; T012–T014 need T008; T015 needs T012–T014
- T016 → T017/T018 → T019; T022/T023 need T018–T019
- T025 → T026; T029/T030 need nothing new beyond Phase 3

### Parallel Opportunities

- Test tasks marked [P] alongside their implementation task: T002, T004, T006, T009,
  T011, T020, T021, T024, T027, T028
- T013 beside T012; T017 beside T016; T031 beside T032
- After Phase 3, US2 and US3 can proceed in parallel (different files: components/schemas
  vs tests/deb-script)

## Parallel Example: User Story 1

```bash
# After T016 lands, run together:
Task: "T017 Clients panel in src/second_hand/components/clients.py"
Task: "T020 endpoint tests in tests/unit/test_api_clients.py"
Task: "T021 panel state tests in tests/unit/test_clients_component.py"
Task: "T024 layout test in tests/browser"
```

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + Phase 3 (US1).** That alone answers "is anyone using my time
server?" on all four distros and satisfies SC-001/SC-002/SC-003. Stop and validate there
(quickstart §§1–4). The assessment's fallback stands: if the appetite runs out, ship
aggregates only — US2 is additive and US3's route-b (disable the unit) already works
mechanically even before its tests exist. Deliver US2, then US3, each with its own
checkpoint; Polish last.

## Notes

- Commit after each task or logical group; run the pre-commit checks before every commit.
- T015 is the designated early-risk task — do not build past Phase 3 before it passes.
- Constrained-field citations resolve to data-model.md entities: Settings (T001),
  ClientRecord / ClientSummary / ServerTotals / ReaderSnapshot (T003, T005, T006, T010,
  T017, T026).
