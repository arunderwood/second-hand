# Concept: Client visibility for a chronyd time server

- **Slug**: client-visibility
- **Created**: 2026-11-26
- **Recommended option**: B — Privileged reader beside the dashboard

## Options

### Option A — Config-unlocked server totals

- **Sketch**: second-hand gains a "Serving" panel with chronyd's server-wide totals: NTP requests received and dropped, rate-limited packets, NTS-KE connections, and interleaved and authenticated counts. It reads them the same unprivileged way it reads tracking today. The panel appears only when chronyd permits it. On chrony 4.7 or later that means the operator adds `opencommands serverstats` to chrony.conf, and second-hand's docs show the line. Elsewhere the panel stays hidden, with a one-line explanation. No client count and no per-client data, because libchrony cannot read the client log.
- **Appetite**: small (days). libchrony already decodes serverstats, so this is a pychrony model plus a dashboard panel.
- **Trade-offs**:
  - **Wins**: no new process, no privilege change, and it fits Principles II and IV exactly.
  - **Sacrifices**: it answers only "is this server doing work, and is it dropping requests?", not "how many clients and who". Distro coverage is **1 of 4** (Ubuntu 26.04), and it needs a chrony.conf edit, which works against Principle III's "out of the box". It meets the dropped-request goal but not the client-count goal.
- **Rabbit holes**:
  - Detecting "not authorised" correctly: the record count succeeds and only the record read fails, which a naive probe mistakes for success.
  - Explaining the missing panel without nagging the operator on every distro where it can't work.

### Option B — Privileged reader beside the dashboard

- **Sketch**: the .deb ships a second, very small service that runs as chrony's own user. Only it can read chronyd's client log and server totals. Its only job is to read them on a fixed, low interval, without resetting anything, and hand the result to the dashboard over a local channel the dashboard can read but not write. The web service keeps its current unprivileged, capability-free unit unchanged. The dashboard shows a "Clients" panel:
  - first, aggregates: how many clients were seen recently, how recently and how often they poll, how many are being rate-limited, and the NTP vs NTS split, plus server totals;
  - optionally, behind the existing on/off flag, a per-client table.

  Turning the feature off disables the reader as well, not just the panel. Works on **4 of 4** target distros with no chrony.conf edit.
- **Appetite**: medium (weeks). Most of the cost is packaging, the second systemd unit and its hardening, tests that run as `_chrony` rather than root, and getting the read-only guarantee right. The UI part is small.
- **Trade-offs**:
  - **Wins**:
    - It is the only option that meets every goal in problem.md: client count, drops, all target distros, no extra privilege in the web process, an off switch, and read-only access.
    - It follows established practice. chrony_exporter runs as chrony's user, node_exporter's textfile pattern has a privileged writer and an unprivileged reader, and chronyd itself drops privileges.
    - It keeps the network-facing process exactly as hardened as today.
  - **Sacrifices**:
    - It breaks Principle II's "prefer a single process" and needs a documented justification or a constitution amendment.
    - It adds a privileged component that must itself be hardened and reviewed (Principle I).
    - Installs that skip the .deb (pip, dev, Docker) get no reader, so the feature is .deb-only unless an operator wires it up.
  - **Risks**: the client-log wire format is documented as unstable across chrony versions.
- **Rabbit holes**:
  - **How the reader gets the client log.**
    - Running the host's own `chronyc -c clients`: its version always matches chronyd's, so it is safe across versions, but it bends Principle IV's "via pychrony".
    - Adding client-log support to pychrony beyond libchrony, the way meta/time did in Go: this keeps Principle IV, but pychrony then owns the compatibility risk of an unstable protocol.

    Either choice is defensible. Choosing both is scope creep.
  - **The handoff channel.** A file the reader rewrites is simplest but can be stale. A local socket is fresher but means another socket unit. Both need permissions that let the `DynamicUser` web service read and nothing else write. That combination is untested (research gap).
  - **Per-client enrichment.** Reusing the sources panel's GeoIP or reverse-DNS lookups on clients could exceed ipwho.is's free limit of 1000 requests a day at pool scale. Leave it out of the first cut.
  - **Pool scale.** A full client log (about 4096 entries by default, up to millions with a larger `clientloglimit`) must not bloat the dashboard or break the under-100 MB memory target.
  - **Never passing the counter-reset option**, and proving it with a test against a real chronyd.

### Option C — Don't build; point to chrony_exporter

- **Sketch**: second-hand adds a short docs section, and perhaps a link in the UI, saying that client and server-load metrics come from chrony_exporter's `--collector.clients` and `--collector.serverstats`, run as chrony's user, with Prometheus and Grafana. The dashboard itself stays unchanged.
- **Appetite**: small (hours to a day).
- **Trade-offs**:
  - **Wins**: zero code or privilege risk. The existing tool already provides well-designed aggregates.
  - **Sacrifices**: second-hand still can't answer "is anyone using my server?". Operators need a whole metrics stack to get that answer, against second-hand's lightweight, homelab-first purpose. Coverage stays at 0 of 4.
- **Rabbit holes**: none of substance.

## Recommendation

**Option B, scoped to aggregates first.** It is the only option that improves every success metric in problem.md:
- **Distro coverage**: 0 → 4 of 4.
- **Web-process hardening score**: unchanged, because the privilege lives in a separate, purpose-built process.
- **Read-only guarantee**: can be tested directly against a real chronyd.
- **Operator effort**: none beyond installing the package.

Option A is cheap but leaves three of four distros blind and doesn't answer the core question ("how many clients?"). Option C answers it only by sending operators to a different product.

Ship aggregates and server totals first; they are what chrony_exporter users asked for and settled on. Add the per-client table as a follow-up behind the flag once the reader exists. That keeps the first appetite at the low end of medium.

The Principle II deviation is the price. Record it as a constitution amendment or a documented justification at specify time, not left implicit.

## Out of Scope (for the recommended option)

- Configuring chronyd (`allow`, `cmdallow`, `opencommands`, `clientloglimit`). Docs may describe these settings.
- Resetting client counters, or any other write to chronyd.
- Keeping client history beyond chronyd's own rolling log.
- Alerting, or replacing Prometheus and chrony_exporter.
- Acting on clients (blocking or rate-limiting).
- GeoIP or reverse-DNS enrichment of clients in the first cut.
- The per-client table in the first cut. It is planned as a flagged follow-up.
- A privileged reader for non-.deb installs (pip, dev, Docker). The panel stays hidden there.
- Supporting chrony versions below 4.0, where the client-log command does not exist.

## Assumptions to Validate

- A systemd unit running as `_chrony` can read the Unix socket on all four target distros. Debian 12's chrony version and socket layout have not been checked.
- A handoff channel exists that a `DynamicUser=yes` unit can read while only the reader can write. Verify with the `docker-systemd` images before committing to the file or the socket design.
- The maintainer accepts a second process under Principle II, by amendment or documented justification.
- The maintainer picks one client-log source: the host's `chronyc` or a pychrony extension. Principle IV must be read to allow it.
- Aggregates are enough for a first release (problem.md open question 1). Per-client detail can wait.
- A low, fixed read interval keeps the reader's load on chronyd and its own footprint negligible, even with a full client log.
- Demand is enough to justify a medium appetite. Today the evidence is the maintainer's own ask plus one upstream issue.
