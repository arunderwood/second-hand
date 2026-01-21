# Tasks: UI Visual Enhancements

**Input**: Design documents from `/specs/003-ui-visual-enhancements/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.yaml

**Tests**: Not explicitly requested in spec. Test tasks omitted. Existing tests should continue to pass.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US7)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Dependencies & Infrastructure)

**Purpose**: Add new dependencies and create foundational infrastructure

- [x] T001 Add geoip2, aiodns, cachetools, asyncache dependencies to pyproject.toml
- [x] T002 [P] Create data package directory with __init__.py at src/second_hand/data/__init__.py
- [x] T003 [P] Bundle GeoLite2-Country.mmdb database in src/second_hand/data/
- [x] T004 [P] Create static/js directory at src/second_hand/static/js/
- [x] T005 Add configuration settings for refresh interval, DNS timeout, cache TTL to src/second_hand/config.py
- [x] T006 Run `uv sync` to install new dependencies

---

## Phase 2: Foundational (Shared Services)

**Purpose**: Core services that multiple user stories depend on

**⚠️ CRITICAL**: US2, US3 depend on these services being complete

- [x] T007 Implement GeoIPService class in src/second_hand/services/geoip.py
  - Singleton pattern with application lifecycle management
  - `lookup(ip)` method returning GeoIPResult dataclass
  - Private IP detection using ipaddress module
  - DEBUG logging for lookup failures (FR-023)
- [x] T008 [P] Implement country_code_to_flag() utility in src/second_hand/utils/__init__.py
  - Unicode regional indicator symbol conversion
  - Handle None/empty/invalid input gracefully
- [x] T009 Implement DNSService class in src/second_hand/services/dns.py
  - aiodns resolver with 3-second timeout (FR-009)
  - TTLCache with 1024 entries, 1-hour TTL (FR-008)
  - `cached_reverse_dns(ip)` async method
  - `batch_reverse_dns(ips)` with semaphore (max 10 concurrent)
  - DEBUG logging for lookup failures (FR-023)
- [x] T010 Create EnrichedSource dataclass in src/second_hand/services/chrony.py
  - Fields: source, hostname, country_code, country_name, country_flag
  - display_name property for "hostname (IP)" format
- [x] T011 Implement source enrichment pipeline in src/second_hand/services/chrony.py
  - `enrich_sources(sources)` async function
  - Integrates GeoIPService and DNSService
  - Returns list of EnrichedSource objects
- [x] T012 Initialize services in FastAPI lifespan in src/second_hand/main.py
  - Create GeoIPService and DNSService at startup
  - Proper cleanup on shutdown

**Checkpoint**: Foundation ready - GeoIP and DNS services operational

---

## Phase 3: User Story 1 - Real-Time Poll Countdown Display (Priority: P1) 🎯 MVP

**Goal**: Live countdown timers showing time until next poll for each NTP source

**Independent Test**: Load dashboard, observe countdown timers decrementing every second, verify auto-refresh after 30 seconds

### Implementation for User Story 1

- [x] T013 [US1] Add data attributes to source row in src/second_hand/components/sources.py
  - `data-poll-interval` with poll interval in seconds
  - `data-last-poll-time` with Unix timestamp
  - `data-last-rx-time` with last receive Unix timestamp
- [x] T014 [US1] Add countdown display element to source row in src/second_hand/components/sources.py
  - Static fallback text showing poll interval (progressive enhancement)
  - CSS class `.countdown` for JS targeting
- [x] T015 [US1] Implement JSON API endpoint GET /api/sources in src/second_hand/main.py
  - Return SourcesResponse per contracts/api.yaml schema
  - Include timestamp, is_synchronized, refresh_interval
  - Handle chronyd connection errors with 503 response
- [x] T016 [US1] Create vanilla JavaScript module at src/second_hand/static/js/dashboard.js
  - `initDashboard()` entry point
  - `updateCountdowns()` function with 1-second setInterval
  - `formatDuration(seconds)` helper for human-readable time
  - `refreshData()` async function fetching /api/sources
  - 30-second auto-refresh interval
- [x] T017 [US1] Include JS script tag in base layout at src/second_hand/components/base.py
  - Add `<script src="/static/js/dashboard.js" defer></script>`
  - Call `initDashboard()` on DOMContentLoaded

**Checkpoint**: Poll countdowns update in real-time; dashboard auto-refreshes every 30 seconds

---

## Phase 4: User Story 7 - Time Since Last Receive Display (Priority: P2)

**Goal**: Live-updating "time since" display for last packet received

**Independent Test**: Load dashboard, observe "Last Rx" values incrementing every second (e.g., "15s ago" → "16s ago")

**Note**: Shares JavaScript infrastructure with US1

### Implementation for User Story 7

- [x] T018 [US7] Add time-since element with data attributes in src/second_hand/components/sources.py
  - CSS class `.time-since` for JS targeting
  - `data-timestamp` with last receive Unix timestamp
  - Static fallback showing formatted duration
- [x] T019 [US7] Add `updateTimeSince()` function to src/second_hand/static/js/dashboard.js
  - Update all `.time-since` elements every second
  - Format as "Xs ago", "Xm Ys ago" etc.
- [x] T020 [US7] Integrate updateTimeSince() into 1-second interval in src/second_hand/static/js/dashboard.js

**Checkpoint**: Last Rx values update in real-time alongside poll countdowns

---

## Phase 5: User Story 2 - Geographic Source Identification (Priority: P2)

**Goal**: Country flags next to NTP sources based on IP geolocation

**Independent Test**: Load dashboard, verify flags appear next to public IPs, hover shows country name

**Depends on**: Phase 2 (GeoIPService)

### Implementation for User Story 2

- [x] T021 [US2] Update _source_row() to display country flag in src/second_hand/components/sources.py
  - Add flag emoji span before/after address
  - Add tooltip with country_name on hover
  - No flag for private IPs or ungeolocatable addresses
- [x] T022 [US2] Add flag tooltip CSS styles in src/second_hand/static/css/style.css
  - `.country-flag` styling
  - `.country-flag[title]` hover tooltip styles
- [x] T023 [US2] Update dashboard route to use enriched sources in src/second_hand/main.py
  - Call `enrich_sources()` before rendering
  - Pass EnrichedSource list to components

**Checkpoint**: Country flags display correctly; private IPs show no flag

---

## Phase 6: User Story 3 - Hostname Resolution Display (Priority: P2)

**Goal**: Resolved hostnames displayed alongside IP addresses

**Independent Test**: Load dashboard, verify "hostname (IP)" format for resolvable addresses

**Depends on**: Phase 2 (DNSService)

### Implementation for User Story 3

- [x] T024 [US3] Update address cell to show display_name in src/second_hand/components/sources.py
  - Use EnrichedSource.display_name property
  - Format: "hostname (IP)" or just "IP" if no hostname
- [x] T025 [US3] Add hostname styling in src/second_hand/static/css/style.css
  - `.source-hostname` for hostname portion
  - `.source-ip` for IP portion (slightly muted)

**Checkpoint**: Hostnames resolve and display correctly; timeouts handled gracefully

---

## Phase 7: User Story 4 - Visual Mode Badges (Priority: P3)

**Goal**: Replace ^, =, # symbols with color-coded badges

**Independent Test**: Load dashboard, verify colored badges for Server/Peer/Reference Clock with hover tooltips

### Implementation for User Story 4

- [x] T026 [US4] Create mode badge component function in src/second_hand/components/sources.py
  - `_format_mode_badge(mode_name)` returning badge Element
  - Map CLIENT→"Server", PEER→"Peer", LOCAL→"Reference Clock"
  - Color classes: server=green, peer=blue, refclock=purple
  - Tooltip with full mode name
- [x] T027 [US4] Replace _format_mode_symbol() call with badge in src/second_hand/components/sources.py
- [x] T028 [US4] Add mode badge CSS styles in src/second_hand/static/css/style.css
  - `.mode-badge` base styles (padding, border-radius, font-size)
  - `.mode-badge--server` green variant
  - `.mode-badge--peer` blue variant
  - `.mode-badge--refclock` purple variant

**Checkpoint**: Mode badges display with correct colors and tooltips

---

## Phase 8: User Story 5 - Selected Source Animation (Priority: P3)

**Goal**: Pulse/glow animation on currently selected NTP source

**Independent Test**: Load dashboard, verify selected source row has visible pulse animation

### Implementation for User Story 5

- [x] T029 [US5] Add @keyframes pulse animation in src/second_hand/static/css/style.css
  - Subtle box-shadow pulse effect
  - 2-second cycle, ease-in-out
- [x] T030 [US5] Apply animation to .source-selected class in src/second_hand/static/css/style.css
- [x] T031 [US5] Add reduced-motion media query fallback in src/second_hand/static/css/style.css
  - Replace animation with static border-left indicator
  - Respect prefers-reduced-motion: reduce

**Checkpoint**: Selected source has visible animation; respects reduced-motion preference

---

## Phase 9: User Story 6 - Reachability Trend Visualization (Priority: P3)

**Goal**: Sparkline-style visualization of 8-bit reachability register

**Independent Test**: Load dashboard, verify sparkline shows 8 dots/bars matching reachability pattern

**Note**: Existing _format_reach_visual() provides foundation; enhance with tooltip

### Implementation for User Story 6

- [x] T032 [US6] Enhance _format_reach_visual() tooltip in src/second_hand/components/sources.py
  - Add title attribute with raw octal value and percentage
  - Format: "Reachability: 377 (100%)"
- [x] T033 [US6] Add sparkline tooltip CSS in src/second_hand/static/css/style.css
  - `.reach-visual[title]` hover styles

**Checkpoint**: Sparkline tooltips show raw value and percentage

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, cleanup, and validation

- [x] T034 Verify progressive enhancement works without JavaScript
  - Disable JS in browser, confirm all data displays statically
- [x] T035 Add error indicator for stale data in src/second_hand/static/js/dashboard.js
  - Show subtle warning when refresh fails
  - Keep displaying previous data
- [x] T036 [P] Add aggregate metrics tracking for lookup failures in src/second_hand/services/dns.py
  - Counter for DNS failures (FR-024)
- [x] T037 [P] Add aggregate metrics tracking for GeoIP misses in src/second_hand/services/geoip.py
  - Counter for GeoIP lookup failures (FR-024)
- [x] T038 Run all pre-commit checks: ruff format, ruff check, ty check, pytest
- [x] T039 Validate quickstart.md scenarios work end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (dependencies installed)
- **US1 (Phase 3)**: Depends on Phase 2 (services ready)
- **US7 (Phase 4)**: Depends on Phase 3 (shares JS infrastructure)
- **US2 (Phase 5)**: Depends on Phase 2 (GeoIPService)
- **US3 (Phase 6)**: Depends on Phase 2 (DNSService)
- **US4 (Phase 7)**: No service dependencies, can start after Phase 1
- **US5 (Phase 8)**: No service dependencies, can start after Phase 1
- **US6 (Phase 9)**: No service dependencies, can start after Phase 1
- **Polish (Phase 10)**: Depends on all user stories complete

### User Story Dependencies

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundational) ──────────────────────────────┐
    │                                                │
    ├──▶ Phase 3 (US1: Countdowns) ──▶ Phase 4 (US7: Time Since)
    │                                                │
    ├──▶ Phase 5 (US2: Flags)                        │
    │                                                │
    ├──▶ Phase 6 (US3: Hostnames)                    │
    │                                                │
    │    ┌──────────────────────────────────────────┤
    │    │ (Can start after Phase 1)                │
    │    ▼                                          │
    │    Phase 7 (US4: Mode Badges)                 │
    │    Phase 8 (US5: Selected Animation)          │
    │    Phase 9 (US6: Reachability Sparkline)      │
    │                                                │
    └────────────────────────────────────────────────┘
                         │
                         ▼
                  Phase 10 (Polish)
```

### Parallel Opportunities

**After Phase 1 completes:**
- T007, T008, T009 can run in parallel (different files)
- T026, T029, T032 (US4, US5, US6) can start immediately (CSS-only changes)

**After Phase 2 completes:**
- US1, US2, US3 can proceed in parallel
- US4, US5, US6 can continue in parallel

**Within each phase:**
- Tasks marked [P] can run in parallel

---

## Parallel Example: Foundation Phase

```bash
# Launch foundational services in parallel:
Task: "Implement GeoIPService in src/second_hand/services/geoip.py"
Task: "Implement country_code_to_flag() in src/second_hand/utils/__init__.py"
Task: "Implement DNSService in src/second_hand/services/dns.py"
```

## Parallel Example: CSS-Only Stories

```bash
# US4, US5, US6 can all start after Phase 1 (no service dependencies):
Task: "Add mode badge CSS styles in src/second_hand/static/css/style.css"
Task: "Add @keyframes pulse animation in src/second_hand/static/css/style.css"
Task: "Add sparkline tooltip CSS in src/second_hand/static/css/style.css"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Real-Time Countdowns)
4. **STOP and VALIDATE**: Verify countdowns work, auto-refresh works
5. Deploy/demo MVP

### Recommended Order (Priority-Based)

1. Phase 1 → Phase 2 (Foundation)
2. Phase 3 (US1) → Phase 4 (US7) - Real-time features
3. Phase 5 (US2) + Phase 6 (US3) - Source identification
4. Phase 7 + Phase 8 + Phase 9 (US4, US5, US6) - Visual polish
5. Phase 10 (Polish)

### Independent Story Testing

Each user story can be tested independently:
- **US1**: Load dashboard, watch countdowns tick, wait 30s for refresh
- **US2**: Load dashboard, check flags appear for public IPs
- **US3**: Load dashboard, verify hostname format
- **US4**: Load dashboard, verify colored badges
- **US5**: Load dashboard, verify pulse on selected row
- **US6**: Hover over sparkline, check tooltip content
- **US7**: Watch "Last Rx" values increment

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Progressive enhancement: All features must work without JS
- Commit after each task or logical group
- Run `uv run ruff format . && uv run ruff check . && uv run ty check src/` before commits
