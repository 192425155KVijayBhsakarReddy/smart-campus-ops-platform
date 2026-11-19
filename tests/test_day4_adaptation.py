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


def test_D4_4_outbox_survives_application_restart_and_drains_queue():
    """
    Verify durable disk-backed outbox intent storage survives complete application restart:
    1. Intent is dispatched during HTTP 503 outage and persisted to disk file.
    2. In-memory buffer instance is terminated/deleted.
    3. Fresh buffer instance re-opens datastore and recovers pending intent.
    4. Persistent retry worker drains queue upon simulated service recovery.
    """
    test_db = os.path.join(os.path.dirname(__file__), "test_restart_outbox.db")
    if os.path.exists(test_db):
        os.remove(test_db)

    try:
        # Phase 1: Application running, experiences remote 503 outage
        outbox1 = OutboxIntentBuffer(test_db)
        res1 = outbox1.dispatch(
            "CALENDAR_SYNC",
            {"booking_id": "BK-2026-MED-99", "campus_id": "CAMPUS-MED", "slot": "10:00-13:50"},
            remote_status_code=503,
            intent_id="INTENT-RESTART-001"
        )
        assert res1["status"] == "BUFFERED"
        assert outbox1.count_intents("PENDING_RETRY") == 1

        # Phase 2: Application crash / restart simulation (destroy outbox1 reference)
        del outbox1

        # Phase 3: Application boots fresh, attaches to same persistent SQLite database
        outbox2 = OutboxIntentBuffer(test_db)
        pending = outbox2.get_pending_intents()
        assert len(pending) == 1
        assert pending[0]["intent_id"] == "INTENT-RESTART-001"
        assert pending[0]["status"] == "PENDING_RETRY"

        # Phase 4: Remote service recovered (HTTP 200) -> Worker processes queue
        def recovered_calendar_api(event_type, payload):
            return True

        worker_result = outbox2.process_outbox_queue(recovered_calendar_api, max_retries=3)
        assert worker_result["processed"] == 1
        assert worker_result["remaining_pending"] == 0
        assert outbox2.count_intents("PROCESSED") == 1
    finally:
        if os.path.exists(test_db):
            os.remove(test_db)


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


def test_D4_6_outbox_duplicate_prevention_and_dead_letter():
    """
    Verify outbox duplicate prevention via unique intent_id,
    and automatic transition to DEAD_LETTER after max retry exhaustion.
    """
    test_db = os.path.join(os.path.dirname(__file__), "test_dead_letter.db")
    if os.path.exists(test_db):
        os.remove(test_db)

    try:
        outbox = OutboxIntentBuffer(test_db)

        # 1. Duplicate Intent Prevention Check
        fixed_id = "INTENT-DEDUP-007"
        res1 = outbox.dispatch("TICKET_SYNC", {"tkt": "TKT-101"}, 503, intent_id=fixed_id)
        assert res1["status"] == "BUFFERED"

        res2 = outbox.dispatch("TICKET_SYNC", {"tkt": "TKT-101"}, 503, intent_id=fixed_id)
        assert res2["duplicate_ignored"] is True
        assert outbox.count_intents() == 1  # Exactly 1 record exists

        # 2. Max Retry Exhaustion -> Dead Letter Transition
        def persistently_failing_service(event_type, payload):
            raise ConnectionResetError("Remote server refused connection")

        # Attempt 1 -> retry_count = 1
        r1 = outbox.process_outbox_queue(persistently_failing_service, max_retries=3)
        assert r1["retried"] == 1
        assert outbox.count_intents("PENDING_RETRY") == 1

        # Attempt 2 -> retry_count = 2
        r2 = outbox.process_outbox_queue(persistently_failing_service, max_retries=3)
        assert r2["retried"] == 1
        assert outbox.count_intents("PENDING_RETRY") == 1

        # Attempt 3 -> retry_count = 3 >= max_retries (3) -> DEAD_LETTER
        r3 = outbox.process_outbox_queue(persistently_failing_service, max_retries=3)
        assert r3["dead_letter"] == 1
        assert r3["remaining_pending"] == 0
        assert outbox.count_intents("DEAD_LETTER") == 1
    finally:
        if os.path.exists(test_db):
            os.remove(test_db)
