"""Validation rules of the shared client-visibility models.

The dashboard trusts nothing in a snapshot it did not validate here, so these
rules are the whole defence between a corrupt file and a 500.
"""

import pytest
from pydantic import ValidationError

from second_hand.clients_model import (
    ClientRecord,
    ClientSummary,
    ReaderSnapshot,
    ServerTotals,
)


def make_summary(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "total_clients": 2,
        "nts_clients": 1,
        "ntp_clients": 1,
        "rate_limited_clients": 0,
        "total_dropped_requests": 0,
        "last_seen_buckets": {"1m": 2, "1h": 0, "1d": 0, "older": 0},
        "poll_interval_buckets": {"<=64s": 1, "<=1024s": 1, ">1024s": 0, "unknown": 0},
    }
    fields.update(overrides)
    return fields


def make_totals(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "ntp_received": 100,
        "ntp_dropped": 0,
        "cmd_received": 5,
        "cmd_dropped": 0,
        "log_records_dropped": 0,
        "nts_ke_accepted": 3,
        "nts_ke_dropped": 0,
        "ntp_authenticated": 10,
        "ntp_interleaved": 0,
    }
    fields.update(overrides)
    return fields


def make_record(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "address": "192.0.2.17",
        "ntp_hits": 42,
        "ntp_drops": 0,
        "ntp_interval": 6,
        "ntp_interval_limited": None,
        "last_ntp_seconds": 12,
        "nts_ke_hits": 0,
        "nts_ke_drops": 0,
        "last_nts_ke_seconds": None,
        "is_nts": False,
        "last_seen_seconds": 12,
    }
    fields.update(overrides)
    return fields


def make_snapshot(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "schema_version": 1,
        "taken_at": 1795900000,
        "interval": 30,
        "status": "ok",
        "reason": None,
        "reason_detail": None,
        "summary": make_summary(),
        "totals": make_totals(),
        "clients": [make_record()],
        "clients_truncated": 0,
    }
    fields.update(overrides)
    return fields


class TestReaderSnapshot:
    def test_valid_snapshot_parses(self) -> None:
        snapshot = ReaderSnapshot.model_validate(make_snapshot())
        assert snapshot.status == "ok"
        assert snapshot.clients[0].address == "192.0.2.17"

    def test_unknown_schema_version_rejected(self) -> None:
        """A version-2 snapshot must fail validation, not half-parse."""
        with pytest.raises(ValidationError):
            ReaderSnapshot.model_validate(make_snapshot(schema_version=2))

    def test_unavailable_without_reason_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReaderSnapshot.model_validate(
                make_snapshot(
                    status="unavailable", summary=None, totals=None, clients=[]
                )
            )

    def test_unavailable_with_reason_parses(self) -> None:
        snapshot = ReaderSnapshot.model_validate(
            make_snapshot(
                status="unavailable",
                reason="client_logging_disabled",
                reason_detail="chronyd was started with noclientlog",
                summary=None,
                totals=None,
                clients=[],
            )
        )
        assert snapshot.reason == "client_logging_disabled"

    def test_unknown_reason_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReaderSnapshot.model_validate(
                make_snapshot(
                    status="unavailable", reason="novel", summary=None, totals=None
                )
            )

    def test_ok_without_data_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReaderSnapshot.model_validate(make_snapshot(summary=None))

    def test_unknown_json_fields_ignored(self) -> None:
        """Fields may be added within schema version 1 (compatibility rule)."""
        snapshot = ReaderSnapshot.model_validate(
            make_snapshot(a_future_field="whatever")
        )
        assert snapshot.schema_version == 1

    def test_negative_truncation_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReaderSnapshot.model_validate(make_snapshot(clients_truncated=-1))


class TestClientRecord:
    def test_negative_counts_rejected(self) -> None:
        for field in ("ntp_hits", "ntp_drops", "nts_ke_hits", "nts_ke_drops"):
            with pytest.raises(ValidationError):
                ClientRecord.model_validate(make_record(**{field: -1}))

    def test_non_address_rejected(self) -> None:
        """Only IP literals: a hostname here means something did a lookup."""
        for address in ("evil.example.com", "", "192.0.2.999", "<script>"):
            with pytest.raises(ValidationError):
                ClientRecord.model_validate(make_record(address=address))

    def test_ipv6_address_accepted(self) -> None:
        record = ClientRecord.model_validate(
            make_record(address="2001:db8:85a3::8a2e:370:7334")
        )
        assert record.address == "2001:db8:85a3::8a2e:370:7334"

    def test_negative_interval_is_a_real_value(self) -> None:
        """chrony allows sub-second polling: 2**-2 is a valid interval."""
        record = ClientRecord.model_validate(make_record(ntp_interval=-2))
        assert record.ntp_interval == -2


class TestClientSummary:
    def test_unknown_bucket_key_rejected(self) -> None:
        """Bucket keys are a fixed enum, so panel and API cannot disagree."""
        buckets = {"1m": 0, "1h": 0, "1d": 0, "older": 0, "1y": 3}
        with pytest.raises(ValidationError):
            ClientSummary.model_validate(make_summary(last_seen_buckets=buckets))

    def test_negative_bucket_count_rejected(self) -> None:
        buckets = {"1m": -1, "1h": 0, "1d": 0, "older": 0}
        with pytest.raises(ValidationError):
            ClientSummary.model_validate(make_summary(last_seen_buckets=buckets))


class TestServerTotals:
    def test_negative_counter_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ServerTotals.model_validate(make_totals(ntp_received=-5))
