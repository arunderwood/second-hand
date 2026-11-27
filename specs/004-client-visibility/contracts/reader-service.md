# Contract: second-hand-reader service

The privileged reader's observable behaviour — what packaging, tests, and the dashboard's
R3 ladder rely on.

## Process contract

- **Entry point**: `python3 second-hand.pex` with `PEX_MODULE=second_hand.reader` (same pex
  as the dashboard; no new artifact).
- **Loop**: every `SECOND_HAND_READER_INTERVAL` seconds (default 30, min 10, fixed — never
  scaled by demand, FR-013): run `chronyc -c -k clients` then `chronyc -c serverstats`
  (fixed argv, no shell, 10 s subprocess timeout), build a `ReaderSnapshot`, publish
  atomically per `reader-snapshot.md`.
- **Read-only invariant (FR-011)**: the only chronyc subcommands ever invoked are `clients`
  (without `-r`) and `serverstats`. No stdin is connected. No IPC, socket, signal, or file
  the reader consumes can alter what it executes — the argv is a module-level constant.
- **Disabled flag**: if `SECOND_HAND_CLIENTS_ENABLED` is false at startup, log one line and
  exit 0 before touching chronyd (FR-016a: unit stays inactive; `Restart=on-failure` does
  not restart a clean exit).
- **Failure mapping**: chronyc failures become `status=unavailable` snapshots, not crashes:
  - `501 Not authorised` → `permission_denied`
  - connection refused / no socket → `chronyd_unreachable`
  - unrecognised command / usage error (chrony < 4.0) → `chrony_too_old`
  - empty/`noclientlog` response → `client_logging_disabled`
  - unparseable output → `parse_error`
  The reader exits non-zero only on programming errors; operational failure is data.
- **Exclusion rule**: rows with `ntp_hits == 0` and `nts_ke_hits == 0` (monitoring-only,
  including the dashboard's own polling) never appear in counts, buckets, or the table.

## Unit contract (`debian/second-hand-reader.service`)

| Directive | Value | Why |
|---|---|---|
| `User=` / `Group=` | `_chrony` / `second-hand-data` | socket access via owner perms; snapshot group-readable |
| `EnvironmentFile=` | `-/etc/default/second-hand` | one off switch for both units (FR-016) |
| `Environment=` | `PEX_MODULE=second_hand.reader` | second entry point in the shared pex |
| `RuntimeDirectory=` | `second-hand-reader`, mode `0750` | snapshot home, gone on stop/reboot |
| `CacheDirectory=` | `second-hand-reader` + `PEX_ROOT` | pex extraction, as the web unit does |
| `UMask=` | `0027` | snapshot file lands `0640` |
| `RestrictAddressFamilies=` | `AF_UNIX` | chronyc → local socket only; add `IPAddressDeny=any` |
| Hardening block | copied from `second-hand.service` | FR-014; `@system-service` already permits fork/exec |
| `After=` / `Wants=` | chrony units, as the web unit | |
| `Restart=` | `on-failure` | clean disable-exit stays down |

`docker/test-deb.sh` enforces a `systemd-analyze security` ceiling for this unit alongside
the existing one for `second-hand.service` (which must stay ≤ its 1.5 baseline — SC-002).

## Packaging contract

- `debian/second-hand.default` → `/etc/default/second-hand` (conffile): documented
  `SECOND_HAND_CLIENTS_ENABLED`, `SECOND_HAND_CLIENTS_TABLE`, `SECOND_HAND_CLIENTS_MAX_ROWS`,
  commented out at their defaults.
- postinst creates system group `second-hand-data` if absent; postrm leaves it (groups are
  cheap, removal races with running units).
- `second-hand.service` gains only `SupplementaryGroups=second-hand-data` and the
  `EnvironmentFile=` line — nothing else in the hardened unit changes (SC-002, FR-010).
- Both units enabled on first install only (`dh_installsystemd` default), so a disabled
  state survives upgrades (FR-016, SC-006).
