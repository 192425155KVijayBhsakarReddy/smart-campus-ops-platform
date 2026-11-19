"""
DAY-4 DESIGN CHALLENGE: MULTI-CAMPUS EVOLUTION, DURABLE OUTBOX & RESILIENCE TEST SUITE
Author: KANDUKURI VIJAY BHASKAR REDDY (Reg No: 192425155)
Course: CSA10 - Software Engineering | CO4: Task 6 Evidence
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from campus_model import MultiCampusPolicyEngine, OutboxIntentBuffer  # noqa: E402


# --------------------------------------------------------------------------
# Task 6 Automated Test Specifications
# --------------------------------------------------------------------------

def test_D4_1_medical_campus_230min_accepted():
    """Verify Medical Campus accepts extended 230-minute surgical simulation using campus_id."""
    assert MultiCampusPolicyEngine.validate_booking("CAMPUS-MED", 230) is True


def test_D4_2_engineering_campus_185min_rejected():
    """Verify Engineering Campus rejects 185 minutes (exceeds 180m limit) using campus_id."""
    with pytest.raises(ValueError, match="exceeds CAMPUS-ENG maximum of 180m"):
        MultiCampusPolicyEngine.validate_booking("CAMPUS-ENG", 185)


def test_D4_3_datacenter_temp_threshold_24():
    """Verify Data Center strict 24.0°C threshold alerting using campus_id."""
    assert MultiCampusPolicyEngine.check_temp_breach("CAMPUS-DC", 24.0) is False
    assert MultiCampusPolicyEngine.check_temp_breach("CAMPUS-DC", 24.01) is True


def test_D4_4_calendar_outage_durable_intent_buffering_and_retry_worker():
    """
    Verify durable disk-backed outbox intent storage during HTTP 503 outage,
    followed by automated retry worker queue drainage upon remote recovery.
    """
    outbox = OutboxIntentBuffer(":memory:")
    
    # 1. External Calendar API experiences HTTP 503 outage -> intent is persisted to ACID storage
    res = outbox.dispatch(
        "CALENDAR_SYNC",
        {"booking_id": "BK-2026-901", "campus_id": "CAMPUS-MED"},
        remote_status_code=503
    )
    assert res["status"] == "BUFFERED"
    assert outbox.count_intents("PENDING_RETRY") == 1

    # 2. Simulated failure retry: Remote endpoint still down -> increments retry_count
    def failing_handler(evt, payload):
        return False
    
    retry_res1 = outbox.process_outbox_queue(failing_handler, max_retries=3)
    assert retry_res1["retried"] == 1
    assert retry_res1["remaining_pending"] == 1

    # 3. Simulated recovery: Remote endpoint returns HTTP 200 -> worker processes queue
    def recovered_handler(evt, payload):
        return True

    retry_res2 = outbox.process_outbox_queue(recovered_handler, max_retries=3)
    assert retry_res2["processed"] == 1
    assert retry_res2["remaining_pending"] == 0
    assert outbox.count_intents("PROCESSED") == 1


def test_D4_5_schema_expand_and_contract_iso8601_backward_compat():
    """
    Verify API v2 Schema Adapter:
    - Normalizes ISO-8601 strings and validates chronological intervals.
    - Adapts legacy v1 payloads lacking campus_id to CAMPUS-ENG with ISO-8601 timestamps.
    - Rejects invalid inverted time ranges.
    """
    # 1. API v2 ISO-8601 payload with canonical campus_id
    v2_payload = {
        "campus_id": "CAMPUS-MED",
        "room": "Surg-Sim-01",
        "start_time": "2026-11-20T10:00:00Z",
        "end_time": "2026-11-20T13:50:00Z"  # 230 minutes
    }
    norm_v2 = MultiCampusPolicyEngine.normalize_and_validate_booking_payload(v2_payload)
    assert norm_v2["campus_id"] == "CAMPUS-MED"
    assert norm_v2["duration_minutes"] == 230
    assert norm_v2["policy_applied"] == "Medical Campus"

    # 2. Legacy v1 payload lacking campus_id and using minute offsets
    legacy_payload = {"room": "Lab-204", "start": 600, "end": 720}  # 120 mins
    norm_v1 = MultiCampusPolicyEngine.normalize_and_validate_booking_payload(legacy_payload)
    assert norm_v1["campus_id"] == "CAMPUS-ENG"
    assert norm_v1["duration_minutes"] == 120
    assert norm_v1["policy_applied"] == "Engineering Campus"
    assert norm_v1["start_time"] == "2026-11-20T10:00:00Z"
    assert norm_v1["end_time"] == "2026-11-20T12:00:00Z"

    # 3. Inverted time range rejection
    bad_payload = {
        "campus_id": "CAMPUS-ENG",
        "start_time": "2026-11-20T12:00:00Z",
        "end_time": "2026-11-20T10:00:00Z"
    }
    with pytest.raises(ValueError, match="must be strictly after start_time"):
        MultiCampusPolicyEngine.normalize_and_validate_booking_payload(bad_payload)
