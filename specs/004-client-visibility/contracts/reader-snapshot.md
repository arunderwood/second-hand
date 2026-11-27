# Contract: Reader Snapshot File

The local channel between `second-hand-reader` and the dashboard (FR-012). The reader is
the only writer; the dashboard (and any curious local admin in the `second-hand-data`
group) only reads.

- **Path**: `/run/second-hand-reader/snapshot.json` (dashboard override:
  `SECOND_HAND_CLIENTS_SNAPSHOT_PATH`)
- **Permissions**: directory `0750 _chrony:second-hand-data`, file `0640 _chrony:second-hand-data`
- **Write discipline**: serialize to `snapshot.json.tmp` in the same directory, `fsync`,
  `rename()`. Readers therefore always see a complete document or the previous one, never
  a partial write.
- **Lifecycle**: `/run` is tmpfs — nothing survives a reboot. systemd removes the directory
  when the unit stops, so a disabled reader leaves no file behind.
- **Encoding**: UTF-8 JSON, one `ReaderSnapshot` object (fields in `../data-model.md`).

## Example — healthy

```json
{
  "schema_version": 1,
  "taken_at": 1795900000,
  "interval": 30,
  "status": "ok",
  "reason": null,
  "reason_detail": null,
  "summary": {
    "total_clients": 12,
    "nts_clients": 3,
    "ntp_clients": 9,
    "rate_limited_clients": 1,
    "total_dropped_requests": 42,
    "last_seen_buckets": {"1m": 7, "1h": 4, "1d": 1, "older": 0},
    "poll_interval_buckets": {"<=64s": 6, "<=1024s": 5, ">1024s": 0, "unknown": 1}
  },
  "totals": {
    "ntp_received": 180211, "ntp_dropped": 42,
    "cmd_received": 9100, "cmd_dropped": 0,
    "log_records_dropped": 0,
    "nts_ke_accepted": 31, "nts_ke_dropped": 0,
    "ntp_authenticated": 5500, "ntp_interleaved": 0
  },
  "clients": [
    {
      "address": "192.0.2.17",
      "ntp_hits": 5202, "ntp_drops": 0,
      "ntp_interval": 6, "ntp_interval_limited": -1,
      "last_ntp_seconds": 12,
      "nts_ke_hits": 0, "nts_ke_drops": 0, "last_nts_ke_seconds": null,
      "is_nts": false, "last_seen_seconds": 12
    }
  ],
  "clients_truncated": 0
}
```

## Example — reader up, data unreadable (FR-017)

```json
{
  "schema_version": 1,
  "taken_at": 1795900000,
  "interval": 30,
  "status": "unavailable",
  "reason": "client_logging_disabled",
  "reason_detail": "chronyd was started with noclientlog",
  "summary": null, "totals": null, "clients": [], "clients_truncated": 0
}
```

## Compatibility rules

- The dashboard rejects any `schema_version` other than 1 by rendering the unavailable
  state ("reader/dashboard version mismatch"), never by erroring.
- Fields may be **added** within version 1; the dashboard's parser ignores unknown fields.
  Removing or retyping a field requires bumping `schema_version` — which in practice means
  upgrading both components together (they ship in one .deb, so this stays theoretical
  except mid-upgrade, where the old file is at most one interval stale).
- A file that is missing, unparseable, or fails model validation is treated exactly like a
  missing reader (R3 ladder step 7), logged at warning once per distinct error.
