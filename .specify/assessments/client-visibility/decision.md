# Decision: Client visibility for a chronyd time server

- **Slug**: client-visibility
- **Decided**: 2026-11-26
- **Verdict**: go
- **Artifacts reviewed**: intake.md, research.md, problem.md, concept.md. Also the maintainer's decisions of 2026-11-26 on the second process, the data source and the flag default.

## Scorecard

| Criterion | Rating | Justification |
|-----------|--------|---------------|
| Problem validity | adequate | The gap is real and checked: second-hand reads no client or serverstats data, and the deployed service can't reach it on 3 of 4 target distros. For a time server, "is anyone using it?" is a basic question. No incident is driving it. |
| Evidence strength | adequate | The technical claims are high-confidence and were checked against a live chronyd 4.6.1, distro packages and upstream source. Demand evidence is weak: the maintainer's own ask plus chrony_exporter #136. For a single-maintainer homelab tool, the maintainer's own need is a legitimate driver, but it is acknowledged here as thin. |
| Value vs. inaction | adequate | Doing nothing costs no outage. Operators keep using `sudo chronyc` or a full Prometheus stack, which goes against second-hand's lightweight purpose. Ubuntu 26.04's `opencommands` covers only part of the problem, and the per-client log remains blocked everywhere. |
| Feasibility / appetite | adequate | Option B has a credible medium appetite with established precedents (chrony_exporter as chrony's user, node_exporter textfile, chronyd's privdrop). The handoff channel under `DynamicUser=yes` is untested, and Debian 12 is unverified. |
| Strategic fit | adequate | It fits Principle IV's "chrony statistics" purpose. The second process deviates from Principle II. The maintainer approved a documented justification, which the constitution allows for non-security violations, and Principle I (least privilege, which outranks II) favours keeping privilege out of the web process. |
| Risk posture | adequate | The main risks are identified, with mitigations sketched but not proven: a new privileged component, an unstable client-log protocol, the counter-reset option, pool-scale memory, and GeoIP rate limits. Exposing client IPs is handled by the flag, as the maintainer directed. |

## Verdict & Rationale

**Go.** Every criterion rates adequate, and none is weak or unknown. Option B is the only shaped option that improves every success metric: distro coverage goes from 0 to 4 of 4, the web unit's hardening score is unchanged, read-only access is testable, and nothing needs configuring beyond installing the package.

The two blockers for strategic fit were settled by the maintainer before this verdict:
- A second process is accepted, with a documented Principle II justification.
- The source of the per-client log is deliberately left to specify/plan.

Demand is the weakest input. The verdict rests on the maintainer's own need and the one upstream issue, not on broad user signal. If the medium appetite overruns, the fallback is to ship aggregates only and stop. Do not expand scope to rescue the per-client table.

## If needs-clarification

Not applicable.

## If go — Handoff to `/speckit-specify`

- **Problem**: People running chronyd as a time server can't tell from second-hand whether anyone is getting time from it, how many clients there are, how often they poll, or whether requests are dropped. On 3 of 4 target distros, the unprivileged service can't reach that data.
- **Chosen approach**: Option B. The .deb ships a small, separately hardened reader service running as chrony's user. It reads chronyd's client log and server totals read-only, at a low fixed interval, and hands them to the dashboard over a local channel the dashboard can read but not write. The web service's unit and privileges are unchanged. The dashboard shows a Clients panel with aggregates and server totals first, and a per-client table after that.
- **Maintainer decisions (2026-11-26)**:
  - A second process is acceptable. The spec records a **documented Principle II justification**, citing Principle I's precedence. No constitution amendment.
  - The per-client log source (the host's `chronyc -c clients` vs a pychrony extension) is **decided in specify/plan**.
  - The flag **defaults to on, including the per-client table**. Turning it off disables the reader too, not just the panel.
  - Security and privacy concerns shape how the feature is offered, not whether.
- **In scope**:
  - client count, poll recency and interval, rate-limited and dropped requests, the NTP/NTS split, and server-wide totals
  - the per-client table, default on
  - the on/off flag
  - the reader service and its packaging and hardening
  - docs for operators
- **Out of scope**:
  - configuring chronyd
  - resetting counters or any other write to chronyd
  - client history beyond chronyd's rolling log
  - alerting, or replacing chrony_exporter
  - acting on clients
  - GeoIP or reverse-DNS enrichment of clients
  - a reader for non-.deb installs, where the panel is hidden
  - chrony versions below 4.0
- **Success metrics**:
  - Distro coverage goes from 0 to 4 of 4.
  - The `systemd-analyze security` score of `second-hand.service` stays within the existing ceiling (baseline 1.5).
  - No setup is needed beyond installing the package.
  - An integration test against a real chronyd proves the counters are unchanged by second-hand's reads.
  - Qualitative: the maintainer answers "are my devices using this?" without opening a shell.
- **Carried-forward open questions**:
  1. Where the client log comes from: the host's `chronyc -c clients` (always matches chronyd's version, but needs a Principle IV justification for the reader) or a pychrony extension (keeps Principle IV, but pychrony owns the unstable protocol).
  2. The handoff channel: a file the reader rewrites, or a local socket. Either way, verify that a `DynamicUser=yes` unit can read it and only the reader can write it, in the `docker-systemd` images.
  3. Whether the per-client table ships in the first release or as a follow-up. With the flag defaulting to on including per-client, decide whether the first release waits for it.
  4. How the reader and dashboard handle pool scale (about 4096 entries by default, millions with a larger `clientloglimit`) within the 100 MB memory target.
  5. Debian 12's chrony version and socket layout (expected 4.3).
  6. The read interval, and how the dashboard shows that the data is a rolling window and how old it is.
