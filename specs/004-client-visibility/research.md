# Research: Client Visibility

**Branch**: `004-client-visibility` | **Date**: 2026-11-26

Resolves the questions the assessment deferred to planning (decision.md "Carried-forward open
questions") plus the unknowns found while filling Technical Context. Evidence from the
assessment research (checked against a live chronyd 4.6.1) is reused, not re-verified.

## R1: Where the reader gets the client log

**Decision**: The reader runs the host's own `chronyc` as a subprocess with a fixed argument
vector — `chronyc -c -n clients -k` and `chronyc -c serverstats` — and parses the CSV output.
Never `-r` (reset), never a shell, never any user-controlled argument. (`-k` is a `clients`
subcommand flag, not a global option — chrony 4.3–4.8 all reject `chronyc -c -k clients` —
and `-n` keeps chronyc from reverse-resolving client addresses, which FR-009 forbids.)

**Rationale**:
- chrony documents the clients/serverstats wire protocol as unstable across versions. The
  distro's `chronyc` always matches the distro's `chronyd`, so version skew is impossible by
  construction. A pychrony implementation would have to track an unstable protocol across
  chrony 4.3–4.8 alone (libchrony has no clients report, and no Python implementation exists
  anywhere — assessment research, confidence high).
- One invocation suffices: `clients -k` reports per-client NTP hits *and* NTS-KE hits
  (added in chrony 4.0, NEWS). That covers both the NTS/NTP split (FR-001) and the
  monitoring-only exclusion — a row with 0 NTP hits and 0 NTS-KE hits is monitoring-only
  and is dropped from every count and the table.
- This is a documented Principle IV deviation ("via pychrony"), confined to the reader
  process. The read-only rule survives intact: the only mutating form is `clients -r`,
  which the reader never passes, and SC-003's integration test proves reads change nothing.

**Alternatives considered**:
- *pychrony extension* (meta/time-style protocol implementation): keeps Principle IV
  literally, but pychrony then owns an officially unstable protocol, and the feature blocks
  on an upstream pychrony release. Rejected for maintenance cost and coupling.
- *chrony ≥ 4.7 `opencommands`*: config-only, no privilege — but covers 1 of 4 target
  distros and requires editing chrony.conf, failing FR-015. Rejected.

## R2: The handoff channel

**Decision**: An atomic snapshot file. The reader serializes one JSON document
(`contracts/reader-snapshot.md`) to `/run/second-hand-reader/snapshot.json` via
write-to-temp + `rename()` on each cycle.

Permissions:
- Reader unit: `User=_chrony`, `Group=second-hand-data`, `RuntimeDirectory=second-hand-reader`,
  `RuntimeDirectoryMode=0750`, `UMask=0027` → directory `0750 _chrony:second-hand-data`,
  file `0640 _chrony:second-hand-data`.
- `second-hand-data` is a static system group created by the package (postinst,
  `getent group || groupadd --system` — groupadd from the essential passwd package;
  Ubuntu 26.04 no longer installs adduser by default). Static groups work with
  `DynamicUser=` units.
- Web unit adds `SupplementaryGroups=second-hand-data` — read access, no write (file and
  directory are writable only by `_chrony`). Nothing network-facing: it is a filesystem
  path, satisfying FR-012.

**Rationale**: at a 30-second cadence a socket buys no freshness over a file, and a file
gives staleness detection for free (the snapshot carries `taken_at`; FR-018). A second
socket unit plus a request protocol is pure added surface. The node_exporter textfile
pattern is the precedent.

**Alternatives considered**: Unix socket served by the reader (rejected: more moving parts,
a listener inside the privileged process, no benefit at this cadence); world-readable file
without the group (rejected: client IPs become readable by every local user, weaker than
the `0750 /run/chrony` status quo).

**Must verify early** (assessment flagged this untested): that a `DynamicUser=yes` unit with
`SupplementaryGroups=` reads the file in the `docker-systemd` images on all four distros.
This is the first packaging task and a quickstart scenario; if it fails, the fallback is
`chmod 0644` on the file (documented, with the local-reader tradeoff recorded).

## R3: Telling "off" (FR-016) from "failed" (FR-017) and "not installed" (FR-019)

A missing snapshot file alone cannot distinguish an operator-disabled reader (panel must be
*absent*) from a crashed one (panel must say *unavailable*) from a non-.deb install (also
*unavailable*).

**Decision**: the dashboard reads the reader unit's state from systemd's documented
on-disk layout — unit file present under `/usr/lib|/lib|/etc/systemd/system` means
installed, the `multi-user.target.wants` symlink means enabled, a `/dev/null` symlink
means masked. No subprocess and no D-Bus: `systemctl show` was the original plan, but the
docker-systemd verification showed dbus-daemon dropping connections from `DynamicUser`
services at the Hello stage (static users work; NSS resolution of the dynamic UID works;
Debian 12, dbus 1.14), so the hardened web unit cannot rely on the bus at all. Three
stat() calls answer the same question with no sandbox interplay, and the unit declares
exactly one [Install] symlink so enablement is one path. The snapshot is consulted before
the unit state: the unit check exists only to disambiguate a missing snapshot, and
checking it first would break installs without systemd (the quickstart dev loop renders a
fresh snapshot with no unit at all). Decision ladder, first match wins:

1. `SECOND_HAND_CLIENTS_ENABLED=false` → absent (FR-016a).
2. Configured chrony address not loopback/Unix-socket → absent (FR-020).
3. Snapshot file fresh → render it (its own `status` may still carry an unavailable reason
   the *reader* saw: chrony too old, client logging off, chronyd unreachable — FR-017).
4. Snapshot stale → render marked stale with age (FR-018).
5. Snapshot missing or invalid → ask systemd why:
   a. `UnitFileState` disabled or masked → absent (FR-016b).
   b. Unit file not found (`UnitFileState` empty / no usable systemctl) → unavailable:
      "reader not installed" (FR-019).
   c. Anything else → unavailable: "reader not running" (FR-017).

`systemctl show` of unit properties is an unprivileged read over D-Bus; `RestrictAddressFamilies`
already allows `AF_UNIX` and `ProtectSystem=strict` permits reading `/run`. **Must verify**
inside the hardened unit in the docker-systemd images (same early task as R2). Fallback if
the sandbox blocks it: ship a packaged-install marker file and accept that an
enabled-but-never-wrote reader renders as absent rather than unavailable (and record that
narrowing in the spec).

An `enabled` but manually stopped reader (`systemctl stop`, no disable) falls through to
rung 5c and shows unavailable — it will return on reboot, so it is not "off".

## R4: One off switch honoured by both components

**Decision**: `/etc/default/second-hand`, shipped as a conffile, loaded by both units via
`EnvironmentFile=-/etc/default/second-hand`. `SECOND_HAND_CLIENTS_ENABLED=false` there turns
everything off: the dashboard hides the panel and endpoints; the reader reads the same
variable at startup and exits 0 immediately, so the unit sits inactive ("the reader MUST NOT
run"). The other route — `systemctl disable --now second-hand-reader` — is native systemd
state. Both survive upgrades: conffiles are preserved by dpkg, and `dh_installsystemd`
enables units only on first install.

## R5: Debian 12 chrony version and feature floor

**Verified 2026-11-26**: Debian 12 ships chrony **4.3-2+deb12u3** (`apt-cache policy` in
`debian:12-slim`). Feature floor across targets:

| Capability | Since | Deb 12 (4.3) | Deb 13 (4.6.1) | U 24.04 (4.5) | U 26.04 (4.8) |
|---|---|---|---|---|---|
| `clients` command | 1.1 | ✅ | ✅ | ✅ | ✅ |
| `clients -k` (NTS-KE columns) | 4.0 | ✅ | ✅ | ✅ | ✅ |
| serverstats base counters | 2.3 | ✅ | ✅ | ✅ | ✅ |
| serverstats NTS-KE/auth fields | 4.0 era | ✅ | ✅ | ✅ | ✅ |
| serverstats interleaved | 4.2 | ✅ | ✅ | ✅ | ✅ |
| serverstats timestamp fields | 4.4 | ❌ | ✅ | ✅ | ✅ |

Everything FR-004 requires exists on all four targets. Timestamp fields are not required
and are ignored.

## R6: CSV parsing across chrony 4.3–4.8

**Decision**: parse positionally from the front with a required minimum field count; ignore
trailing extra fields. serverstats grew only by appending (4.2 interleaved, 4.4 timestamps),
and the fields FR-004 needs all predate 4.3. `clients -k` rows are fixed at 10 fields
(address, NTP hits/drops/interval/interval-after-limit/last, NTS-KE hits/drops/interval/last).
Any row that fails to parse marks the snapshot `parse_error` rather than publishing partial
numbers. The exact column layout on each distro version is asserted by the integration/deb
test matrix, not assumed — the protocol is unstable by upstream's own statement, and the
matched-chronyc choice (R1) plus per-distro CI is the mitigation.

## R7: Pool scale within the memory budget

**Decision**: the reader streams chronyc's stdout line by line, folding each row into
aggregates incrementally, and keeps only the top `SECOND_HAND_CLIENTS_MAX_ROWS` (default
100) records by recency (bounded heap). The snapshot file is therefore O(max_rows), not
O(log size); the dashboard never sees more than the cap plus aggregate numbers
(`total_clients` tells the panel how many more exist — FR-006). A default-size log
(~4096 entries) streams in milliseconds; a million-entry log stays bounded on both sides.

## R8: Read interval and staleness

**Decision** (confirms the spec's assumptions): reader interval fixed at 30 s
(`SECOND_HAND_READER_INTERVAL`, clamped to ≥ 10), independent of dashboard viewers
(FR-013). The snapshot records `taken_at` and `interval`; the dashboard marks data stale
when `age > 3 × interval` (FR-018) and always shows the age.

## R9: Reader packaging and runtime

**Decision**: the reader is a new module in the same package (`second_hand.reader`),
shipped in the existing pex. Its unit runs the same pex with
`Environment=PEX_MODULE=second_hand.reader`. No new Debian binary package, no second
build artifact; the .deb grows one unit file, one conffile, and a postinst group. The
reader imports only stdlib + the shared snapshot models (pydantic is already in the pex);
it never imports FastAPI/uvicorn.

**Alternatives considered**: a separate minimal package or script (rejected: two artifacts
to version together, no benefit); asyncio in the reader (rejected: a sleep loop + subprocess
needs none of it).

## R10: Reader hardening

**Decision**: `second-hand-reader.service` copies the web unit's hardening block (FR-014)
minus what it does not need, with differences:
- `User=_chrony` (static, owned by the chrony package) instead of `DynamicUser` — the whole
  point is inheriting chronyd's socket access; `/run/chrony` is `0750 _chrony:_chrony`.
- `RestrictAddressFamilies=AF_UNIX` only (chronyc → local socket; no DNS, no HTTP).
- No listener, no ports; `IPAddressDeny=any` is addable since it needs no network at all.
- `CapabilityBoundingSet=`, `NoNewPrivileges=yes`, `ProtectSystem=strict`, same syscall
  filter (`@system-service` covers fork/exec for the chronyc subprocess).
- `ReadWritePaths` none beyond `RuntimeDirectory`.

`docker/test-deb.sh` gains a second `systemd-analyze security` check with its own ceiling
for the reader unit, so its score is pinned exactly as the web unit's is (SC-002 protects
the web unit; this keeps the new privileged unit honest too).
