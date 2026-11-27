# Idea Intake: Show NTP clients served by this chronyd

- **Slug**: client-visibility
- **Created**: 2026-11-26
- **Source**: pasted text (repo: second-hand)
- **Type**: new-capability

## Idea (as captured)

> right now second hand exposes a lot of data around the chrony server itself but it doesn't expose any information about the clients connected to it receiving time. Explore the client data that's accessible and lets look at how we can expose it through second hand

## Restated

second-hand currently shows chronyd's own state (tracking, sources, sourcestats, RTC) but nothing about the hosts that query it for time. The idea is to find out what client-side data chronyd makes reachable and how the dashboard could present it.

## Origin & Context

- **Raised by**: the maintainer, in a Claude Code session on 2026-11-26.
- **Trigger**: [NEEDS CLARIFICATION: was there a specific question about who uses the server (e.g. pool membership, LAN devices, load), or is this general completeness?]
- **Related code**: no client or serverstats handling exists in `src/second_hand/`; no GitHub issues mention it.
- **Prior findings on record** (from an earlier session, verified against chrony 4.6.1 and re-checked against upstream source on 2026-11-26 — recorded here as input for research, not a verdict):
  - libchrony (and so pychrony) has no `clients` report; the per-IP table from `chronyc clients` is not reachable through the current stack.
  - libchrony does expose `serverstats` (aggregate counters), but chronyd answers 501 Not authorised over the command port unless `opencommands serverstats` is set, which needs chrony ≥ 4.7. Debian trixie ships 4.6.1.
  - The Unix command socket requires root or `_chrony`; `DynamicUser=yes` in `debian/second-hand.service` rules it out.

## First-Glance Unknowns

- [NEEDS CLARIFICATION: Is aggregate data (serverstats: total NTP requests, drops, interleaved/timestamp counts) useful on its own, or is the per-client table the real goal?]
- [NEEDS CLARIFICATION: Which chrony versions must this work on? The 4.7+ `opencommands` path excludes current Debian stable packages.]
- [NEEDS CLARIFICATION: Are there client data sources outside chronyd's command protocol worth considering (chrony logs, packet capture, conntrack)?]
- Privacy of client IPs: answered by the maintainer on 2026-11-26. second-hand is not really a public dashboard, and the feature can be turned off with a flag, so privacy is a design constraint rather than a reason not to build it. [NEEDS CLARIFICATION: Should the flag default to on or off?]
- [NEEDS CLARIFICATION: Can privilege separation get around the socket restriction? Research common patterns where a small helper runs with the rights to read chronyd's Unix socket (as `_chrony` or root) and hands a narrow, read-only result to the network-facing web process, which stays unprivileged. Examples to look at: a systemd socket-activated helper, a sidecar exporter like chrony_exporter, a setuid/capability helper, polkit, or a periodic job writing a file.]
- [NEEDS CLARIFICATION: Is changing upstream (a libchrony clients report, or a pychrony-side cmdmon implementation) in scope?]
- [NEEDS CLARIFICATION: Expected client scale — a handful of LAN devices or thousands of pool clients — affects whether a table, a summary, or both makes sense.]
