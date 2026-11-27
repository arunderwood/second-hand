# Problem Definition: Operators can't see who their chronyd is serving

- **Slug**: client-visibility
- **Created**: 2026-11-26
- **Inputs used**: intake.md, research.md, and the maintainer's guidance in this session (security is a design constraint)

## Problem Statement

People who run chronyd as a time server cannot tell from second-hand whether anyone is getting time from it, how many clients there are, how often they poll, or whether chronyd is dropping their requests. second-hand shows only chronyd's own sync state, so answering any of these means a root shell and `chronyc clients`/`serverstats`, or a separate Prometheus stack. On three of the four target distros, the deployed service cannot reach this data at all, because chronyd gives it only to root or `_chrony`.

## Affected Users & Stakeholders

- **Users**:
  - **Homelab operators whose chronyd serves time to a LAN.** They want to confirm their devices are actually using it, and spot clients that have stopped polling or are being rate-limited. — [research: Users & Demand. Group size unknown, ASSUMPTION]
  - **Operators of a public or pool server.** They want server-wide load and drop signals. The fixed-size client log (about 4096 entries by default) matters most to them. — [research: Data & Constraints. Whether second-hand has such users: NEEDS CLARIFICATION]
  - **The maintainer**, as an operator of their own server. — [intake: Origin]
- **Stakeholders**:
  - **The maintainer.** Decides scope, owns the constitution, and also maintains pychrony, so a pychrony-side change is within their control. — [research: Prior Art]
  - **Upstream chrony and libchrony** (Miroslav Lichvar). Control whether the clients report and remote access to it become available without privilege. No decision power over second-hand, but they set its constraints. — [research: Prior Art, Data & Constraints]
  - **Hosts running second-hand.** Affected by any change to the service's privilege, process count or footprint (constitution Principles I and II). — [research: Data & Constraints]

## Goals

- From second-hand alone, an operator can tell whether their chronyd is serving clients, roughly how many, and whether any requests are being dropped or rate-limited.
- This works on the distros second-hand targets, including those whose packaged chrony is older than 4.7.
- The network-facing web process gains no privilege: it keeps no capabilities, no setuid, and the same hardening.
- Interactions with chronyd stay read-only. Nothing second-hand does changes chronyd's counters or state.
- An operator who doesn't want client data shown can turn it off. — [maintainer, 2026-11-26]
- The shown data is honest about its limits: it is a rolling window of recently seen clients, not a complete history.

## Non-Goals

- Configuring chronyd for the operator (editing `allow`, `cmdallow`, `opencommands` or `clientloglimit`). Principle IV keeps second-hand from configuring chrony. Documenting what an operator may need to set is still in scope.
- Keeping client history beyond what chronyd itself holds. second-hand has no persistence.
- Alerting, or replacing Prometheus and chrony_exporter for operators who already run them.
- Managing access control: blocking, rate-limiting or otherwise acting on clients.
- Treating security or privacy concerns as a reason not to offer the feature. They shape how it is offered. — [maintainer, 2026-11-26]

## Success Metrics

- **Distro coverage**: the number of target distros (Debian 12, Debian 13, Ubuntu 24.04, Ubuntu 26.04) where a packaged install can show client data. Baseline: **0 of 4**.
- **Web-process privilege**: the `systemd-analyze security` score of `second-hand.service` stays within the ceiling the .deb tests already enforce. Baseline: **1.5**, and the ceiling check passes.
- **Operator effort**: steps beyond installing the package needed to see client data. Baseline: no path exists. The target is still to be decided (see Open Questions).
- **Read-only guarantee**: chronyd's client counters are unchanged by second-hand reading them, as checked by an integration test against a real chronyd. Baseline: not applicable, since nothing reads them today.
- **Qualitative**: the maintainer uses it on their own server to answer "are my devices using this?" without opening a shell. Baseline: they have to open a root shell.

## Cost of Inaction

second-hand stays a view of chronyd's sync state only. Operators who want client data keep using `sudo chronyc clients`/`serverstats`, or deploy chrony_exporter, Prometheus and Grafana, which already offer aggregate client metrics. Nothing breaks, and there is no known incident or complaint behind this idea. The cost is a gap in what the dashboard can answer: for a time *server*, "is anyone using it?" is a basic question. Ubuntu 26.04 (chrony 4.8) can grant non-root access by config today, and other distros will follow as they move to chrony 4.7 or later. So part of the access problem may shrink on its own over time.

## Open Questions

1. [NEEDS CLARIFICATION: Is aggregate visibility (counts, poll intervals, drops, server-wide totals) enough, or must an operator also be able to identify individual clients?]
2. [NEEDS CLARIFICATION: Should the on/off flag default to on or off?]
3. [NEEDS CLARIFICATION: How much setup beyond installing the package is acceptable to see client data (none, one config step, or editing chrony.conf)? This sets the target for the operator-effort metric.]
4. [NEEDS CLARIFICATION: Does Principle II ("Prefer a single-process architecture") allow a second, privileged process, or would that need a constitution amendment?]
5. [NEEDS CLARIFICATION: Does Principle IV's "via pychrony" allow pychrony to grow support outside libchrony, or must all chrony access go through libchrony?]
6. [NEEDS CLARIFICATION: Which chrony versions must be supported? The clients command needs chrony 4.0 or later, and its wire format is documented as unstable across versions.]
7. [NEEDS CLARIFICATION: Does second-hand have pool-scale users, or is it LAN-only in practice? How many clients does the maintainer's own server have?]
8. [NEEDS CLARIFICATION: chrony version on Debian 12 is unverified. It is expected to be 4.3.]
