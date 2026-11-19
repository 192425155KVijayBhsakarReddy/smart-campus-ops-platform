"""
DAY-4 DESIGN CHALLENGE: MULTI-CAMPUS EVOLUTION & RESILIENCE TEST SUITE
Author: KANDUKURI VIJAY BHASKAR REDDY (Reg No: 192425155)
Course: CSA10 - Software Engineering | CO4: Task 6 Evidence
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import campus_model as m  # noqa: E402


class MultiCampusPolicyEngine:
    """Multi-campus policy evaluator enforcing campus-specific rules."""
    POLICIES = {
        "CAMPUS-ENG": {"max_duration": 180, "temp_threshold": 28.0},
        "CAMPUS-MED": {"max_duration": 240, "temp_threshold": 26.0},
        "CAMPUS-DC":  {"max_duration": 120, "temp_threshold": 24.0},
    }

    @classmethod
    def validate_booking(cls, campus_code: str, duration_minutes: int) -> bool:
        policy = cls.POLICIES.get(campus_code, cls.POLICIES["CAMPUS-ENG"])
        if duration_minutes < 1 or duration_minutes > policy["max_duration"]:
            raise ValueError(f"Duration {duration_minutes}m exceeds {campus_code} maximum of {policy['max_duration']}m")
        return True

    @classmethod
    def check_temp_breach(cls, campus_code: str, value: float) -> bool:
        policy = cls.POLICIES.get(campus_code, cls.POLICIES["CAMPUS-ENG"])
        return value > policy["temp_threshold"]


class OutboxIntentBuffer:
    """Durable Outbox buffer for external service integration during outages."""
    def __init__(self):
        self.queue = []

    def dispatch(self, event_type: str, payload: dict, remote_status_code: int):
        if remote_status_code == 200:
            return {"status": "SYNCED", "remote_id": "EXT-9901"}
        elif remote_status_code in [502, 503, 504]:
            intent = {"event_type": event_type, "payload": payload, "status": "PENDING_RETRY", "retries": 1}
            self.queue.append(intent)
            return {"status": "BUFFERED", "intent": intent}
        else:
            raise RuntimeError(f"Unexpected remote error: HTTP {remote_status_code}")


# --------------------------------------------------------------------------
# Task 6 Automated Test Specifications
# --------------------------------------------------------------------------

def test_D4_1_medical_campus_230min_accepted():
    """Verify Medical Campus accepts extended 230-minute surgical simulation."""
    assert MultiCampusPolicyEngine.validate_booking("CAMPUS-MED", 230) is True


def test_D4_2_engineering_campus_185min_rejected():
    """Verify Engineering Campus rejects 185 minutes (exceeds 180m limit)."""
    with pytest.raises(ValueError, match="exceeds CAMPUS-ENG maximum of 180m"):
        MultiCampusPolicyEngine.validate_booking("CAMPUS-ENG", 185)


def test_D4_3_datacenter_temp_threshold_24():
    """Verify Data Center strict 24.0°C threshold alerting."""
    assert MultiCampusPolicyEngine.check_temp_breach("CAMPUS-DC", 24.0) is False
    assert MultiCampusPolicyEngine.check_temp_breach("CAMPUS-DC", 24.01) is True


def test_D4_4_calendar_outage_intent_buffering():
    """Verify remote HTTP 503 outage buffers intent with zero local data loss."""
    outbox = OutboxIntentBuffer()
    res = outbox.dispatch("CALENDAR_SYNC", {"booking_id": "BK-2026-901", "campus": "CAMPUS-MED"}, remote_status_code=503)
    assert res["status"] == "BUFFERED"
    assert len(outbox.queue) == 1
    assert outbox.queue[0]["status"] == "PENDING_RETRY"


def test_D4_5_schema_expand_and_contract_backward_compat():
    """Verify backward compatibility: legacy v1 payload defaults to CAMPUS-ENG."""
    legacy_payload = {"room": "Lab-204", "start": 600, "end": 720}  # 120 mins
    duration = legacy_payload["end"] - legacy_payload["start"]
    campus = legacy_payload.get("campus_code", "CAMPUS-ENG")
    assert MultiCampusPolicyEngine.validate_booking(campus, duration) is True
