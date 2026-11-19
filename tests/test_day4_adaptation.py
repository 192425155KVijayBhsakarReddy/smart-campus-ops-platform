"""
DAY-4 DESIGN CHALLENGE: MULTI-CAMPUS EVOLUTION & RESILIENCE TEST SUITE
Author: KANDUKURI VIJAY BHASKAR REDDY (Reg No: 192425155)
Course: CSA10 - Software Engineering | CO4: Task 6 Evidence
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# Imported directly from core platform domain model (not defined in test)
from campus_model import MultiCampusPolicyEngine, OutboxIntentBuffer  # noqa: E402


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
    """Verify backward compatibility adapter: legacy v1 payload lacking campus_code defaults safely to CAMPUS-ENG policy."""
    legacy_payload = {"room": "Lab-204", "start": 600, "end": 720}  # 120 mins
    normalized = MultiCampusPolicyEngine.normalize_and_validate_booking_payload(legacy_payload)
    assert normalized["campus_code"] == "CAMPUS-ENG"
    assert normalized["duration_minutes"] == 120
    assert normalized["policy_applied"] == "Engineering Campus"
    assert normalized["room"] == "Lab-204"
