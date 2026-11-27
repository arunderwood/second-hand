# Idea Research: Show NTP clients served by this chronyd

- **Slug**: client-visibility
- **Created**: 2026-11-26
- **Evidence confidence (overall)**: medium. Whether the data can be reached, and how, is high: checked against a live chronyd and upstream sources. Demand is low: one maintainer and one external issue.

## Users & Demand

- The only stated demand inside this project is the maintainer's own ask. No second-hand GitHub issue mentions clients or serverstats, and nothing in `src/second_hand/` reads them. — [source: `gh issue list --search client`, grep of `src/`] (confidence: high)
- Outside the project, chrony_exporter issue #136 ("Client statistics", 2025-11-04) asked for exactly this data, and the upstream maintainer replied "PRs welcome". The issue asked for aggregates (client count, histograms of last-seen/interval/drops, NTP vs NTS split) and said per-client detail is "probably too detailed for metrics collecting". It was closed by PR #181 (merged 2026-08-12, shipped in v0.14.0). — [source: github.com/SuperQ/chrony_exporter/issues/136, /pull/181] (confidence: high)
- That is one stated request from one external user. Nothing observed shows how many people would use the data. — [ASSUMPTION] (confidence: low)
- Most homelab chronyd instances serve a handful of LAN clients, or none if `allow` is never set. Pool servers serve thousands. Which group second-hand's users fall into is unknown. — [ASSUMPTION] (confidence: low)

## Prior Art

### Getting the data

- **chrony_exporter (Go) already ships a clients collector.** It uses `REQ_CLIENT_ACCESSES_BY_INDEX` from Meta's `facebook/time` (`meta/time`) chrony package, added there in facebook/time#522 (2026-06-04). It does not go through libchrony. It is off by default (`--collector.clients`), needs chrony ≥ 4.0, and exports **only aggregates with no per-client labels**. Hits and drops are gauges rather than counters, because the fixed-size client log reuses records and the sums can go down. — [source: chrony_exporter README.md and collector/clients.go; facebook/time commit 65b1d50] (confidence: high)
- **No Python implementation of the clients command exists.** GitHub code search for `REQ_CLIENT_ACCESSES_BY_INDEX3` in Python returns 0 hits. In Go, the only implementation is `meta/time`. — [source: api.github.com code search, 2026-11-26] (confidence: medium, since code search indexes only part of GitHub)
- **libchrony (upstream C, used by pychrony) has no clients report.** Its README lists `serverstats` but not `clients`. — [source: gitlab.com/chrony/libchrony README.adoc; prior-session memory, verified 2026-10-31] (confidence: high)
- **pychrony is maintained by the same person as second-hand** (`arunderwood`, github.com/arunderwood/pychrony). It wraps libchrony via cffi, and its connection class exposes only tracking, sources, sourcestats and rtcdata. A pychrony-side addition would not wait on a third party. Bypassing libchrony would, however, mean implementing chrony's wire protocol in pychrony. — [source: `.venv/.../pychrony-3.0.3.dist-info/METADATA`, `pychrony/_core/_bindings.py`] (confidence: high)
- **netdata** collects chrony over UDP via the protocol, but gets `serverstats` by running `chronyc serverstats` through `ndsudo`, a setuid-root helper with a fixed allowlist of commands. netdata does not collect clients. — [source: netdata `go.d/collector/chrony/metadata.yaml`, `src/collectors/utils/ndsudo.c`] (confidence: high)
- **Telegraf** `inputs.chrony` gets `serverstats` only over the Unix socket. Its docs say adding the telegraf user to the `chrony` group is enough. — [source: telegraf plugins/inputs/chrony/README.md] (confidence: medium). This contradicts what was observed on Debian; see Data & Constraints.

### Privilege-separation patterns (the intake's research ask)

The pattern in common: a small process has the rights to read chronyd's Unix socket, and the unprivileged, network-facing web process only reads its narrow output.

| Pattern | Precedent | Fit with the current unit | Evidence |
|---|---|---|---|
| **A separate collector process running as chrony's user** | chrony_exporter: "needs to run as root or the same user as chrony", plus `--collector.chmod-socket` when it runs as root | The web process stays unprivileged and is not changed. Adds a second process and unit. | cited (README); confidence high |
| **Setuid helper with a fixed command allowlist** | netdata `ndsudo` → `chronyc serverstats` | Conflicts with `NoNewPrivileges=yes` and `RestrictSUIDSGID=yes` in `debian/second-hand.service`. Setuid cannot raise privileges under `NoNewPrivileges`. | unit file cited; the setuid/NNP interaction is standard Linux behaviour [ASSUMPTION, high] |
| **Group membership** | Telegraf docs (`chrony` group) | **Does not work on Debian/Ubuntu.** `/run/chrony` is `0750 _chrony:_chrony` and the socket is `0755`, so group members get no write access. A `_chrony` group member was refused in the earlier session. | observed in container; memory 2026-10-31; confidence high |
| **Privileged periodic job writes a file; the web process reads it** | node_exporter textfile collector (`*.prom` files written by batch jobs) | Fully decoupled, and the web process only needs read access. Data is only as fresh as the job interval. | README cited; confidence high |
| **systemd relay**: a helper unit with `User=_chrony` that serves results on its own socket (`SocketMode=`/`SocketGroup=`, or socket activation), with the web unit given access via `SupplementaryGroups=` | General systemd practice; no chrony-specific precedent found | Fits `DynamicUser=yes`, and `RestrictAddressFamilies` already allows `AF_UNIX`. | [ASSUMPTION: from systemd unit semantics, not fetched or tested] (confidence: medium) |
| **No helper: open the command remotely** | chrony ≥ 4.7 `opencommands clients serverstats` + `cmdallow 127.0.0.1` | Removes the need for privilege, but requires editing chrony.conf and a new enough chrony. | chrony.conf.adoc and NEWS cited; confidence high |

Internal precedent: chronyd itself is started as root and drops to `_chrony` (`-u _chrony`, `+PRIVDROP` in the build flags). — [source: `chronyd --version` in the test container] (confidence: high)

## Market & Context

- Today, operators who want client data either run `chronyc clients` / `chronyc serverstats` as root by hand, or run chrony_exporter with Prometheus and Grafana. Both already exist, and the exporter route already gives aggregate client metrics. — [source: chronyc.adoc; chrony_exporter README] (confidence: high)
- If nothing is built, second-hand stays a view of chronyd's own sync state. Operators who care about clients use the tools above. There is no known incident or complaint behind this idea. — [ASSUMPTION] (confidence: medium)

## Data & Constraints

**What the data looks like** (observed against chrony 4.6.1 in `second-hand-test:latest`, after generating client traffic with `chronyd -Q`):

- `chronyc -c clients` gives one CSV row per client: address, NTP packets, NTP drops, interval, interval after rate limiting, last NTP, then command (or NTS-KE with `-k`) packets, drops, interval, last. — [source: container probe; chronyc.adoc `clients`] (confidence: high)
- `chronyc serverstats` gives 17 server-wide counters (NTP/command received and dropped, client-log records dropped, NTS-KE accepted/dropped, authenticated, interleaved, and timestamp sources). — [source: container probe] (confidence: high)
- The client log has a fixed size: `clientloglimit` defaults to 512 KiB, about 4096 addresses, and when full, chronyd reuses the oldest records. `noclientlog` turns it off entirely. — [source: chrony.conf.adoc] (confidence: high)
- The log only records hosts that passed `allow`/`cmdallow`, and it excludes accesses over the Unix socket. — [source: chronyc.adoc `clients`] (confidence: high)
- `clients -r` **resets the counters**. A collector must never pass `-r`, or it would break the constitution's read-only rule (Principle IV). — [source: chronyc.adoc] (confidence: high)

**Who can read it** (container probe):

| Caller | Transport | `clients` | `serverstats` |
|---|---|---|---|
| root | Unix socket | ✅ | ✅ |
| `_chrony` | Unix socket | ✅ | (not probed; same rule applies) |
| `nobody` | Unix socket | ❌ refused (cannot traverse the `0750` dir) | ❌ |
| root or any user | UDP 127.0.0.1:323 | ❌ `501 Not authorised` | ❌ `501 Not authorised` |
| any | UDP, chrony 4.6.1 with `opencommands` | n/a: `Invalid directive` | n/a |

**chrony version on each target distro** (`apt-cache policy chrony`, 2026-11-26):

| Distro | chrony | `opencommands` (≥ 4.7) |
|---|---|---|
| Debian 13 (trixie) | 4.6.1-3+deb13u2 | ❌ |
| Ubuntu 24.04 | 4.5-1ubuntu4.2 | ❌ |
| Ubuntu 26.04 | 4.8-2ubuntu1 | ✅ |
| Debian 12 (bookworm) | not checked (expected 4.3) [ASSUMPTION] | ❌ (expected) |

Of four target distros, only Ubuntu 26.04 has a config-only path. The others need a privileged reader.

**Other constraints:**

- **Protocol stability**: chrony's docs state that the protocol for `clients` and `serverstats` "is not considered stable" across chronyc/chronyd versions, unlike tracking and sources. — [source: chrony.conf.adoc `opencommands`] (confidence: high)
- **Upstream activity**: chrony 4.9 "Reduce impact of client logging on server performance". 4.8 added `chronyc -u` to drop root privileges and hid the chronyc socket "to mitigate unsafe permissions change". — [source: chrony NEWS] (confidence: high)
- **Current service hardening**: `DynamicUser=yes`, `NoNewPrivileges=yes`, `RestrictSUIDSGID=yes`, `CapabilityBoundingSet=` (empty), and a `systemd-analyze security` ceiling enforced by the .deb tests. The service binds `0.0.0.0:8000`. — [source: debian/second-hand.service] (confidence: high)
- **Constitution**: Principle I requires least privilege and forbids command injection. Principle II says "Prefer a single-process architecture". Principle III requires sensible defaults and simple setup. Principle IV says chrony access is "read-only queries via pychrony". — [source: .specify/memory/constitution.md] (confidence: high)
- **Dev and deployed environments differ**: integration tests run as root over the Unix socket (`cmdport 0`), so client data would pass in CI even though the deployed service cannot reach it. — [source: docker/Dockerfile.test, docker-compose.test.yml] (confidence: high)

## Evidence Against the Idea

- **Privacy and attack surface (a design constraint, not a blocker).** A per-client table publishes LAN or internet client IPs on a dashboard bound to `0.0.0.0`. chrony's docs warn that these reports "can be potentially useful to attackers". ntpd's `monlist` (CVE-2013-5211) is the well-known case of a client-list command being abused. Even chrony_exporter chose aggregates only. — [source: chrony.conf.adoc; debian/second-hand.service; chrony_exporter PR #181. CVE cited from general knowledge, not fetched] (confidence: high)
  - **Maintainer position (2026-11-26):** second-hand is not really a public dashboard, and the client feature can be turned off with a flag. Security concerns shape how the feature is offered; they do not decide whether it is offered. — [source: maintainer, this session]
- **Every path conflicts with the constitution or with setup.**
  - A helper process conflicts with "single process".
  - `chronyc` as a subprocess, or a hand-written protocol client, conflicts with "via pychrony".
  - `opencommands` requires the operator to edit chrony.conf and run chrony ≥ 4.7, which only one target distro ships.
  - A setuid helper conflicts with the unit's hardening.
  - [source: constitution; unit file; distro table above] (confidence: high)
- **Maintenance cost.** The clients protocol is officially unstable across versions. A pychrony implementation that bypasses libchrony would own that compatibility burden alone. — [source: chrony.conf.adoc `opencommands`] (confidence: medium)
- **Thin demand.** One maintainer ask and one external issue, and that external need is now met by chrony_exporter. — [source: issue searches above] (confidence: medium)
- **The data has caveats that are easy to misread.** The log is a fixed ring of about 4096 entries, records only allowed hosts, and can drop records. Counts can go down and "connected" is really "seen recently". — [source: chrony.conf.adoc; chrony_exporter README] (confidence: high)
- **Many homelab servers may show an empty panel.** Without an `allow` line, chronyd serves no clients. — [ASSUMPTION] (confidence: low)

## Gaps & Open Questions

- [NEEDS CLARIFICATION: Is aggregate data (counts, last-seen and interval histograms, serverstats) enough, or does the maintainer want a per-client table? This decides privacy exposure and the data path.]
- [NEEDS CLARIFICATION: Is a second process or unit acceptable under Principle II, or should the constitution be amended for a privileged helper?]
- [NEEDS CLARIFICATION: Should "via pychrony" be read as "pychrony grows a client-accesses implementation" (the maintainer owns pychrony) or as "libchrony only"?]
- [NEEDS CLARIFICATION: The systemd relay pattern (a helper unit as `_chrony` with its own socket, and `SupplementaryGroups=` on a `DynamicUser` unit) is unverified. It needs a test in the `docker-systemd` images before it is relied on.]
- [NEEDS CLARIFICATION: chrony version on Debian 12 was not checked.]
- [NEEDS CLARIFICATION: How many clients does the maintainer's own server have (LAN only, or pool)? This sets realistic scale for the UI.]
- [NEEDS CLARIFICATION: Is reading data from an operator-run job (textfile pattern) acceptable for "Simple Setup", or must it work out of the box from the .deb?]

## Sources

- https://gitlab.com/chrony/chrony/-/raw/master/doc/chrony.conf.adoc (host: gitlab.com, policy: allowlisted)
- https://gitlab.com/chrony/chrony/-/raw/master/doc/chronyc.adoc (host: gitlab.com, policy: allowlisted)
- https://gitlab.com/chrony/chrony/-/raw/master/NEWS (host: gitlab.com, policy: allowlisted)
- https://gitlab.com/chrony/libchrony/-/raw/main/README.adoc (host: gitlab.com, policy: allowlisted)
- https://raw.githubusercontent.com/SuperQ/chrony_exporter/main/README.md (host: raw.githubusercontent.com, policy: confirmed-by-user)
- https://raw.githubusercontent.com/SuperQ/chrony_exporter/main/go.mod (host: raw.githubusercontent.com, policy: confirmed-by-user)
- https://raw.githubusercontent.com/SuperQ/chrony_exporter/main/collector/clients.go (host: raw.githubusercontent.com, policy: confirmed-by-user)
- https://raw.githubusercontent.com/influxdata/telegraf/master/plugins/inputs/chrony/README.md (host: raw.githubusercontent.com, policy: confirmed-by-user)
- https://raw.githubusercontent.com/netdata/netdata/master/src/go/plugin/go.d/collector/chrony/metadata.yaml (host: raw.githubusercontent.com, policy: confirmed-by-user)
- https://raw.githubusercontent.com/netdata/netdata/master/src/collectors/utils/ndsudo.c (host: raw.githubusercontent.com, policy: confirmed-by-user)
- https://raw.githubusercontent.com/prometheus/node_exporter/master/README.md (host: raw.githubusercontent.com, policy: confirmed-by-user)
- api.github.com via `gh`: SuperQ/chrony_exporter issue #136, PR #181, commit history of `collector/clients.go`; facebook/time commit history of `ntp/chrony/packet.go`; code search for `REQ_CLIENT_ACCESSES_BY_INDEX` (host: api.github.com, policy: confirmed-by-user)
- Local: container probe of chrony 4.6.1 (`second-hand-test:latest`); `apt-cache policy chrony` in `debian:13` and `ghcr.io/fauust/docker-systemd:ubuntu-24.04` / `ubuntu-26.04`; repo files `debian/second-hand.service`, `docker/Dockerfile.test`, `.specify/memory/constitution.md`; installed pychrony 3.0.3 metadata and bindings.

All web fetches were pinned to a resolved public address, with redirects disabled. chrony-project.org was approved but not needed: gitlab.com carries the same doc sources.
