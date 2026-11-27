# Feature Specification: Client Visibility

**Feature Branch**: `feat/client-visibility`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "Use the handoff in .specify/assessments/client-visibility/decision.md (assessment slug client-visibility, verdict go). Problem: people running chronyd as a time server can't tell from second-hand whether anyone is getting time from it, how many clients there are, how often they poll, or whether requests are dropped; on 3 of 4 target distros the unprivileged service can't reach that data. Approach: the .deb ships a small, separately hardened reader service running as chrony's user that reads chronyd's client log and server totals read-only at a low fixed interval and hands them to the dashboard over a local channel the dashboard can read but not write; the web service's unit and privileges stay unchanged. The dashboard gains a Clients panel: aggregates (client count, poll recency/interval, rate-limited/dropped requests, NTP/NTS split) plus server-wide totals, and a per-client table. A flag turns the feature off, defaulting to on including the per-client table; off disables the reader too. Out of scope: configuring chronyd, resetting counters or any write to chronyd, history beyond chronyd's rolling log, alerting, acting on clients, GeoIP/rDNS enrichment of clients, a reader for non-.deb installs, chrony below 4.0. Success: 0 to 4 of 4 target distros show client data; second-hand.service security score stays within its ceiling (1.5); no setup beyond installing the package; an integration test against real chronyd proves reads don't change counters. Carried-forward open questions are listed in decision.md."

**Assessment**: `.specify/assessments/client-visibility/` (intake, research, problem, concept, decision — verdict **go**)

## Clarifications

### Session 2026-11-26

- Q: Should hosts that only sent monitoring requests (such as this machine's own dashboard polling chronyd) count as clients? → A: No. Only hosts that requested time (NTP or NTS-KE) count and are listed; monitoring-only hosts appear only in server-wide totals.
- Q: What should the Clients panel do when the dashboard is pointed at a chronyd on another machine? → A: Hide the panel entirely, with no notice.
- Q: How does an operator turn client data off, so the reader stops and it stays off through upgrades? → A: Either way works: one dashboard setting honoured by both components, or disabling the reader service. Each turns everything off.
- Q: Can operators hide only the per-client table and keep the aggregates? → A: Yes. A separate setting, on by default, hides the table and leaves client addresses out of the data endpoints, while aggregates and totals keep showing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See whether my server is serving anyone (Priority: P1)

An operator runs chronyd as a time server for their network and has installed the second-hand package. They open the dashboard and, without opening a shell or editing any configuration, see a Clients panel that tells them how many clients have recently fetched time from this server, how recently and how often those clients poll, how many are being rate-limited, how many use NTS versus plain NTP, and server-wide totals of requests received and dropped.

**Why this priority**: This is the core question the feature exists to answer — "is anyone using my time server, and is it keeping up?" — and on three of the four target distributions it is unanswerable today without root access. It delivers value on its own even if nothing else ships.

**Independent Test**: Install the package on a host whose chronyd serves at least one other machine, generate NTP traffic from that machine, open the dashboard, and confirm the panel shows a non-zero client count and matching request totals — with no steps beyond installing the package.

**Acceptance Scenarios**:

1. **Given** a packaged install on any target distribution and a chronyd that has served three distinct clients in the last hour, **When** the operator opens the dashboard, **Then** the Clients panel shows three clients seen, their combined request count, and the server-wide totals.
2. **Given** some clients are being rate-limited by chronyd, **When** the operator views the panel, **Then** it shows how many clients had requests dropped and the total dropped requests.
3. **Given** a mix of NTS and plain-NTP clients, **When** the operator views the panel, **Then** the client count is split into NTS and NTP.
4. **Given** the dashboard is left open, **When** new clients poll the server, **Then** the panel updates on the dashboard's normal refresh cycle without a page reload.
5. **Given** a fresh install, **When** the operator compares the network-facing service's privileges before and after this feature, **Then** they are unchanged.

---

### User Story 2 - Identify which devices are using it (Priority: P2)

The operator wants to confirm a specific device — a camera, a NAS, a laptop — is actually getting time from this server, or spot one that has stopped polling. Below the aggregates, the panel lists each client the server has seen recently, with its address, request count, dropped requests, typical poll interval, and how long ago it was last seen.

**Why this priority**: Aggregates answer "is it working?"; the table answers "for which devices?". It is valuable but builds on the same data as Story 1, and Story 1 is useful without it.

**Independent Test**: With two known devices polling the server, open the dashboard and confirm both addresses appear with plausible last-seen and interval values; stop one device and confirm its last-seen age grows on later refreshes.

**Acceptance Scenarios**:

1. **Given** the feature and the per-client table setting are both at their defaults (on), **When** the operator opens the dashboard, **Then** the per-client table is shown beneath the aggregates.
2. **Given** a device stopped polling twenty minutes ago, **When** the operator views the table, **Then** that device's last-seen age reads about twenty minutes.
3. **Given** chronyd's client log holds more clients than the table is set to display, **When** the operator views the table, **Then** the most recently active clients are shown and the panel states how many more exist.

---

### User Story 3 - Turn client data off (Priority: P3)

An operator who does not want client addresses or counts shown — for example because the dashboard is reachable by people who should not see them — turns the feature off, either with one dashboard setting or by disabling the reader service. Client data disappears from the dashboard and its data endpoints, the privileged reader stops running, and it stays off through package upgrades.

**Why this priority**: Required so the feature can default to on, but it is a control on Stories 1–2 rather than value on its own.

**Independent Test**: Turn the feature off by each route in turn — the setting, then disabling the reader — restart, and confirm the Clients panel and client data are absent from both the page and the data endpoints, and that the reader is not running. Upgrade the package and confirm it is still off.

**Acceptance Scenarios**:

1. **Given** the feature is turned off by either route, **When** anyone loads the dashboard or its data endpoints, **Then** no client data and no Clients panel appear.
2. **Given** the feature is turned off by either route, **When** the operator inspects running services, **Then** the privileged reader is not running.
3. **Given** the feature is turned off, **When** the package is upgraded, **Then** it is still off.
4. **Given** the feature is turned back on, **When** the services restart, **Then** the panel returns without further setup.
5. **Given** only the per-client table setting is turned off, **When** anyone loads the dashboard or its data endpoints, **Then** aggregates and server totals appear, but no client address or per-client record does.

---

### Edge Cases

- **chronyd serves no one** (no clients permitted by its access configuration): the panel shows zero clients — the dashboard's own monitoring traffic never counts as a client — and a one-line hint that chronyd only serves clients its configuration allows — not an error.
- **chronyd has client logging disabled**: the panel says client logging is off in chronyd rather than showing zero.
- **chronyd older than 4.0**: client data is unavailable; the panel says the installed chrony version is too old for client data.
- **Reader enabled but not working** (crashed, failing, or missing on a non-packaged install). A reader the operator deliberately disabled is "off" (FR-016), not this case. The panel shows a compact "client data unavailable" state with the reason; the rest of the dashboard is unaffected.
- **Reader data goes stale**: the panel shows how old the data is; past a staleness threshold it marks values as stale rather than presenting them as current.
- **Client log full** (chronyd recycles the oldest entries): the panel indicates the list is capped by chronyd's log size, so counts are a rolling window, not a complete census.
- **Client counts go down** between refreshes because chronyd recycled entries: shown as-is, never as an error or negative delta.
- **Large client logs** (thousands of entries on a pool server): the page stays responsive and the dashboard stays within its memory budget.
- **chronyd restarts**: counters reset to zero on chronyd's side; the panel reflects that without error.
- **IPv6 client addresses**: displayed in full without breaking the table layout.
- **Dashboard pointed at a remote chronyd**: the Clients panel and all client data are absent, exactly as when the feature is off, with no notice. The reader only ever reads the chronyd on its own machine, so showing its data beside another server's stats would be misleading.

## Requirements *(mandatory)*

### Functional Requirements

**Data shown**

- **FR-001**: The dashboard MUST show, when client data is available, the number of distinct clients in chronyd's client log, split into NTS and plain-NTP clients. A client is a host with at least one NTP request or NTS-KE connection; hosts that only sent monitoring requests (including this machine's own dashboard) are not clients and MUST be excluded from every count, distribution, and the per-client table.
- **FR-002**: The dashboard MUST show the distribution of how recently clients were last seen and how often they poll, in a form an operator can read at a glance (e.g. buckets such as "last minute / last hour / last day").
- **FR-003**: The dashboard MUST show how many clients had requests dropped by rate limiting and the total number of dropped client requests.
- **FR-004**: The dashboard MUST show chronyd's server-wide totals: NTP requests received and dropped, monitoring requests received and dropped, NTS-KE connections accepted and dropped, authenticated and interleaved NTP requests, and client-log records dropped.
- **FR-005**: Unless turned off by FR-021, the dashboard MUST show a per-client table listing, for each client: address, NTP requests, dropped requests, average poll interval, time since last request, and NTS-KE connections where present.
- **FR-006**: The per-client table MUST be ordered by most recently seen and MUST cap the number of rows displayed, stating how many further clients exist beyond the cap.
- **FR-007**: The panel MUST make clear that client data is chronyd's rolling log of recently seen clients, and MUST indicate when that log is full and older clients have been dropped.
- **FR-008**: Client data MUST refresh on the dashboard's existing refresh cycle, and MUST be available from the dashboard's data endpoints in the same way source data is today.
- **FR-009**: Client addresses MUST be shown as addresses only — no hostname, geolocation, or other third-party lookup is performed on clients.

**Access and privilege**

- **FR-010**: Client data MUST be obtained by a separate reader component that holds the privilege needed to query chronyd for it; the network-facing dashboard service MUST NOT gain any privilege, capability, group, or file access to chronyd's control channel.
- **FR-011**: The reader MUST issue only read-only monitoring queries to chronyd. It MUST NEVER reset counters, change configuration, or issue any control command, and MUST NOT expose any way for another process to make it do so.
- **FR-012**: The reader MUST pass its results to the dashboard through a local channel that the dashboard can read but not write, and that is not reachable from the network.
- **FR-013**: The reader MUST query chronyd at a fixed, low frequency that does not depend on how many people view the dashboard.
- **FR-014**: The reader MUST be hardened to the same standard as the dashboard service, limited to the access it needs to query chronyd and publish its results.

**Packaging, configuration, and failure handling**

- **FR-015**: On each target distribution (Debian 12, Debian 13, Ubuntu 24.04, Ubuntu 26.04), installing the package MUST be sufficient for client data to appear; no change to chronyd's configuration or any other manual step may be required.
- **FR-016**: The feature MUST default to on. The per-client table, controlled separately by FR-021, also defaults to on. An operator MUST be able to turn it off in either of two ways, each with the same result: (a) one setting in the dashboard's usual configuration, honoured by both the dashboard and the reader, or (b) disabling the reader service through the system's service manager. When off by either route, the reader MUST NOT run, the Clients panel MUST be absent (not shown as unavailable), and no client data may appear on the page or data endpoints. The off state MUST survive package upgrades. A reader that is enabled but has failed is not "off", and is covered by FR-017.
- **FR-017**: When the feature is on but client data is unavailable (reader enabled but not working, chrony too old, client logging disabled, chronyd unreachable), the panel MUST show a short, specific reason, and the rest of the dashboard MUST keep working.
- **FR-018**: When the reader's latest data is older than a staleness threshold, the panel MUST show the data's age and mark it stale.
- **FR-019**: Installs without the package's reader (source, development, container) MUST continue to work; the Clients panel shows the unavailable state rather than failing.
- **FR-020**: When the dashboard's configured chronyd address is not on this machine (anything other than a loopback address or a local socket path), the Clients panel and all client data MUST be absent from the page and data endpoints, with no unavailable notice.
- **FR-021**: A second setting, on by default and independent of FR-016, MUST control the per-client table. When it is off, the table MUST be absent and no individual client address or per-client record may appear on the page or data endpoints, while aggregates (FR-001–FR-003) and server totals (FR-004) keep showing.

### Key Entities

- **Client record**: one host in chronyd's client log with at least one NTP request or NTS-KE connection — its address, NTP request and drop counts, average poll interval, time since last NTP request, NTS-KE connection count and drops, and monitoring request counts. Represents "recently seen", not "currently connected".
- **Client summary**: aggregates over all client records — total clients, NTS/NTP split, last-seen and poll-interval distributions, rate-limited client count, total drops, and whether the log is at capacity.
- **Server totals**: chronyd's server-wide counters since it started — requests received and dropped by kind, NTS-KE connections, authenticated and interleaved requests, and client-log records dropped.
- **Reader snapshot**: one published result from the reader — the client summary, client records, server totals, the time it was taken, and an availability status with a reason when data could not be read.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On all 4 target distributions (baseline: 0 of 4), a fresh package install on a host serving at least one client shows a correct client count within two dashboard refresh cycles, with zero setup steps beyond installing the package.
- **SC-002**: The network-facing dashboard service's hardening exposure rating does not increase and stays within the ceiling the package tests already enforce (baseline: 1.5).
- **SC-003**: Across 10 consecutive reads with no new client traffic, chronyd's per-client and server-wide counters are identical before and after — verified against a real chronyd.
- **SC-004**: With a full default-size client log (about 4,000 clients), the dashboard page loads in under 2 seconds and the dashboard's memory use stays under 100 MB.
- **SC-005**: An operator can answer "how many devices used this server in the last hour?" and "is device X still getting time from it?" within 10 seconds of opening the dashboard, without a shell.
- **SC-006**: With the feature turned off by either route, no client data appears in any dashboard page or data endpoint, and the reader is not running, after a single restart — and both remain true after a package upgrade.

## Assumptions

- **Target scale**: Most installs serve a handful to a few hundred LAN clients; pool-scale logs (thousands of entries) must stay responsive but are not the design centre. Default per-client row cap is 100, configurable.
- **Freshness**: The reader's fixed interval matches the dashboard's default refresh interval (30 seconds). Data is marked stale after three missed intervals.
- **Unavailable vs. hidden**: When the feature is on but data cannot be read, the panel shows a compact unavailable state with the reason (in line with the constitution's "Clear Error Messages"), rather than disappearing silently. When the feature is off (FR-016) or the dashboard is pointed at a remote chronyd (FR-020), the panel is absent.
- **Monitoring accesses**: Per-client monitoring-request counts are folded into server-wide totals rather than given their own table columns; they are mostly the host's own monitoring traffic.
- **Supported chrony**: 4.0 and later. Older versions get the "too old" unavailable state.
- **Packaging**: The reader ships only in the .deb; other install methods show the unavailable state (FR-019).
- **Constitution**: The separate reader deviates from Principle II ("prefer a single process"). The maintainer approved a documented justification on 2026-11-26, resting on Principle I (least privilege), which takes precedence. The plan MUST record that justification and the security impact analysis the constitution's amendment and compliance rules require. Whether the reader's chrony access satisfies Principle IV ("via pychrony") depends on the data-source choice deferred to planning.
- **Deferred to planning** (from the assessment's decision record): where the reader gets the per-client log (the host's own chrony client tool vs. an extension to pychrony), the exact local handoff channel and its permissions, and verifying both on all four target distributions — including Debian 12, whose chrony version is not yet confirmed.
