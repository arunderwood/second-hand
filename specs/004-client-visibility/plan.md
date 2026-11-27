# Implementation Plan: Client Visibility

**Branch**: `004-client-visibility` | **Date**: 2026-11-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-client-visibility/spec.md`

## Summary

Give operators a Clients panel — client count with NTS/NTP split, last-seen and
poll-interval distributions, rate-limiting drops, server-wide totals, and a capped
per-client table — on all four target distros with zero setup beyond installing the .deb.
The data is collected by a new, separately hardened reader service (`second-hand-reader`)
running as `_chrony`, which shells out to the host's version-matched `chronyc` with a fixed
read-only argv every 30 s and publishes an atomic JSON snapshot that the unchanged,
unprivileged web service reads via a supplementary group. One conffile flag (or disabling
the reader unit) turns the whole feature off; a second flag hides only the per-client
table. Design decisions and their evidence: [research.md](./research.md).

## Technical Context

**Language/Version**: Python; deployed on distro python3 3.11–3.15 (pex), developed on 3.15.
3.11 is the syntax floor.

**Primary Dependencies**: FastAPI, uvicorn, htpy, pydantic (all existing). The reader adds
**no new dependencies**: stdlib `subprocess` + the shared pydantic models. pychrony stays
as-is (it has no clients support; see Constitution Check, Principle IV deviation).

**Storage**: one tmpfs snapshot file, `/run/second-hand-reader/snapshot.json`
(`0640 _chrony:second-hand-data`, atomic rename; [contracts/reader-snapshot.md](./contracts/reader-snapshot.md)).
No database, no persistence across reboots — chronyd's rolling log is the source of truth.

**Testing**: pytest (unit, with chronyc/systemctl mocked and per-version CSV fixtures);
dockerized integration tests against real chronyd (SC-003 counter-invariance); Playwright
layout tests; `docker/test-deb.sh` matrix across Debian 12/13, Ubuntu 24.04/26.04 with two
`systemd-analyze security` ceilings.

**Target Platform**: Debian 12 (chrony 4.3, verified), Debian 13 (4.6.1), Ubuntu 24.04
(4.5), Ubuntu 26.04 (4.8); reader ships only in the .deb. Non-.deb installs render the
unavailable state (FR-019).

**Project Type**: web service + a sibling background service in the same package/pex
(second systemd unit, entry via `PEX_MODULE=second_hand.reader`).

**Performance Goals**: page load < 2 s and dashboard < 100 MB with a full ~4,000-entry
client log (SC-004); reader cost independent of viewer count (FR-013).

**Constraints**: web unit's hardening score stays within its 1.5 ceiling with zero new
privilege (SC-002, FR-010); reader strictly read-only, proven against real chronyd
(SC-003, FR-011); snapshot bounded to O(max_rows) regardless of log size (research R7).

**Scale/Scope**: design centre is a handful to a few hundred LAN clients; pool-scale logs
(up to millions of entries with a raised `clientloglimit`) must stay bounded, not fast.

## Constitution Check

*GATE: evaluated before Phase 0; re-evaluated after Phase 1 design — both passes below.*

| Principle | Verdict | Notes |
|---|---|---|
| I. Security First | PASS | See security impact analysis below. No new privilege in the web process; reader least-privilege and hardened; fixed-argv subprocess (no injection path); snapshot validated as untrusted input. |
| II. Lightweight Design | **DEVIATION — justified** | Second process. Maintainer-approved 2026-11-26 (decision.md); Principle I outranks II. Complexity Tracking below. Memory: reader is a sleep-loop + subprocess, snapshot capped; combined footprint stays within the 100 MB target. |
| III. Simple Setup | PASS | Install-only on all four distros (FR-015); defaults on; both off-switches documented in one conffile; actionable unavailable-states instead of silent failure. |
| IV. Focused Scope | PASS on scope, **DEVIATION on "via pychrony"** | Displaying chrony statistics only; nothing configures chrony. The reader uses `chronyc` (fixed argv) instead of pychrony — justified below. Read-only is preserved and integration-tested (SC-003). |
| V. Learning-Friendly | PASS | Typed models shared between processes; structured logging in the reader; the R3 decision ladder implemented as one documented function. |

### Security impact analysis (required by Governance §2 for Principle I-adjacent changes)

**What gains privilege**: only `second-hand-reader`, a new unit running as `_chrony` — an
existing distro-managed user — with the hardening block of the web unit, `AF_UNIX` only,
no listener, no inbound channel of any kind ([contracts/reader-service.md](./contracts/reader-service.md)).
Its attack surface is: (a) output of `chronyc`, parsed defensively; (b) its environment
file, root-owned. It accepts no input from the network or the web process — the channel is
one-way by filesystem permissions (web side can read, not write).

**What does not change**: `second-hand.service` keeps every hardening directive; the only
unit edits are `SupplementaryGroups=second-hand-data` and `EnvironmentFile=`, neither of
which grants chronyd access (the group guards the snapshot file only). The deb test
enforces both score ceilings so regressions are caught mechanically (SC-002).

**New exposure created**: client IP addresses become visible on the dashboard. Mitigations
are the spec's: feature flag (default on, FR-016), separate table flag that strips
addresses from page and endpoints (FR-021), remote-chronyd suppression (FR-020), no
enrichment/lookups on client IPs (FR-009). Residual risk — a reachable dashboard shows LAN
client IPs by default — is the maintainer's accepted, documented position (decision.md).

**Injection review**: both subprocess argvs are module constants; no user data ever reaches
`subprocess`, satisfying the constitution's prohibition. The dashboard's one new subprocess
(`systemctl show`, fixed argv, R3) is likewise constant.

### Post-design re-check (after Phase 1)

No new violations introduced by the design artifacts. The data model keeps addresses out
of the API when FR-021 is off at the serialization boundary (not in the template), the
snapshot contract versions itself, and the only deviations remain the two justified above.

## Project Structure

### Documentation (this feature)

```text
specs/004-client-visibility/
├── plan.md              # This file
├── research.md          # Phase 0: R1–R10 decisions
├── data-model.md        # Phase 1: ClientRecord/Summary/ServerTotals/ReaderSnapshot
├── quickstart.md        # Phase 1: validation scenarios
├── contracts/
│   ├── reader-snapshot.md   # local channel (file) contract
│   ├── api-clients.md       # GET /api/clients + panel rendering rules
│   └── reader-service.md    # process, unit, and packaging contract
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/second_hand/
├── clients_model.py         # NEW shared pydantic models (both processes import this)
├── reader/
│   ├── __init__.py          # NEW
│   ├── __main__.py          # NEW entry point (PEX_MODULE=second_hand.reader)
│   ├── collect.py           # NEW chronyc invocation + CSV parsing + aggregation
│   └── publish.py           # NEW atomic snapshot writer
├── services/
│   └── clients.py           # NEW dashboard side: R3 ladder, snapshot load, staleness
├── components/
│   ├── clients.py           # NEW Clients panel (htpy)
│   └── dashboard.py         # panel wired into the page
├── schemas.py               # + ClientsResponse
├── config.py                # + clients_* / reader_interval settings
├── main.py                  # + GET /api/clients
└── static/js/dashboard.js   # + clients refresh on the existing cycle

debian/
├── second-hand-reader.service   # NEW hardened reader unit
├── second-hand.default          # NEW conffile → /etc/default/second-hand
├── second-hand.service          # + SupplementaryGroups, EnvironmentFile
├── control                      # description mentions the reader
├── postinst                     # NEW: create second-hand-data group
└── rules                        # install the new unit + default file

docker/test-deb.sh               # reader checks, off-route checks, second score ceiling

tests/
├── unit/
│   ├── test_reader_collect.py   # NEW: CSV fixtures per chrony version, exclusion rule
│   ├── test_reader_publish.py   # NEW: atomicity, disabled-exit
│   ├── test_clients_service.py  # NEW: R3 ladder, staleness, FR-021 redaction
│   └── test_clients_component.py# NEW: panel states
├── integration/
│   └── test_clients_integration.py  # NEW: SC-003 counter invariance vs real chronyd
└── browser/                     # clients panel layout cases (IPv6, row cap, 4k fixture)
```

**Structure Decision**: single project, as today. The reader is a subpackage of
`second_hand` shipped in the same pex — two processes, one codebase, one artifact — because
the .deb must version both sides of the snapshot contract together
(contracts/reader-snapshot.md, compatibility rules).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Second process/unit (Principle II "prefer single process") | Only `_chrony`/root can read chronyd's client log on 3 of 4 target distros; privilege must live somewhere, and Principle I (which outranks II) forbids putting it in the network-facing process (FR-010). Maintainer approved 2026-11-26. | In-process access would require granting the web service chronyd socket access (raises its exposure, breaks SC-002); `opencommands` works on 1 of 4 distros and needs manual chrony.conf edits (breaks FR-015); setuid helpers conflict with `NoNewPrivileges`. |
| `chronyc` subprocess instead of pychrony (Principle IV "via pychrony") | libchrony/pychrony has no clients report; the wire protocol is officially unstable across versions, and the distro's chronyc always matches its chronyd (research R1). | Extending pychrony means owning an unstable binary protocol across chrony 4.3–4.8 in a cffi wrapper and coupling this feature to upstream pychrony releases. The constitution's intent behind "via pychrony" — safe, read-only, injection-free access — is met: fixed argv, no `-r`, SC-003 proves counters unchanged. |
