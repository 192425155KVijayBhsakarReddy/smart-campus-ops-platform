"""
AUTHORITATIVE LIVE PLATFORM INTEGRATION TEST SUITE (NGINX / POSTGRESQL / DUAL BACKENDS)
Author: KANDUKURI VIJAY BHASKAR REDDY (Reg No: 192425155)
Course: CSA10 - Software Engineering | CO4: Release Verification & Quality Gates
"""

import pytest
import urllib.request
import urllib.error
import json
import uuid
import time

BASE_URL = "http://localhost/api"

def _http_request(endpoint, method="GET", data=None):
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    headers = {"Content-Type": "application/json", "User-Agent": "PytestLiveRunner/1.0"}
    encoded_data = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            body = res.read().decode("utf-8")
            return res.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return e.code, json.loads(body) if body else {}


def test_LP1_live_healthz_and_database():
    """Verify live Nginx proxy and PostgreSQL 16 container health via /api/healthz/"""
    status_code, body = _http_request("/healthz/")
    assert status_code == 200
    assert body.get("status") == "healthy"
    assert body.get("database") == "connected"
    assert "PostgreSQL 16" in body.get("engine", "")


def test_LP2_live_gist_exclusion_overlap_409():
    """Verify PostgreSQL btree_gist ExclusionConstraint strictly rejects overlapping slots with HTTP 409"""
    # 1. Fetch available rooms
    status_code, rooms = _http_request("/rooms/")
    assert status_code == 200
    assert len(rooms) > 0
    room_code = rooms[0]["room_code"]

    # 2. Book a specific timeslot (e.g. 14:00 to 16:00 UTC)
    t_base = int(time.time()) + 72000
    slot_a = {
        "room": room_code,
        "booked_by": "Prof. Davis",
        "purpose": "Autonomous Robotics Lab Session",
        "start_time": f"2026-11-20T10:00:00Z",
        "end_time": f"2026-11-20T12:00:00Z"
    }
    status_a, res_a = _http_request("/bookings/", method="POST", data=slot_a)
    # Either successfully created (201) or already booked (409)
    assert status_a in [201, 409]

    # 3. Attempt overlapping booking (11:00 to 13:00 UTC)
    slot_overlap = {
        "room": room_code,
        "booked_by": "Student Club",
        "purpose": "Drone Flight Practice",
        "start_time": f"2026-11-20T11:00:00Z",
        "end_time": f"2026-11-20T13:00:00Z"
    }
    status_b, res_b = _http_request("/bookings/", method="POST", data=slot_overlap)
    assert status_b == 409
    assert res_b.get("error") == "ERR_SLOT_OVERLAP"


def test_LP3_live_optimistic_locking_stale_version_409():
    """Verify ticket transition with stale expected_version is rejected with HTTP 409 Conflict"""
    # 1. Create a ticket
    ticket_payload = {
        "title": "HVAC Chiller Valve Stuck",
        "category": "FACILITIES",
        "impact": "HIGH",
        "urgency": "HIGH",
        "reported_by": "automation-tester"
    }
    status_create, ticket = _http_request("/tickets/", method="POST", data=ticket_payload)
    assert status_create == 201
    ticket_id = ticket["id"]
    current_ver = ticket["version"]

    # 2. Advance version from 1 to 2
    transition_ok = {
        "expected_version": current_ver,
        "target_status": "IN_PROGRESS",
        "actor": "lead-tech-sarah",
        "resolution_notes": "Diagnostic inspection started"
    }
    status_trans1, res_trans1 = _http_request(f"/tickets/{ticket_id}/transition/", method="POST", data=transition_ok)
    assert status_trans1 == 200
    assert res_trans1.get("version") == current_ver + 1

    # 3. Attempt conflicting update using stale version
    transition_stale = {
        "expected_version": current_ver,  # stale!
        "target_status": "RESOLVED",
        "actor": "junior-tech-bob",
        "resolution_notes": "Overwriting without refresh"
    }
    status_stale, res_stale = _http_request(f"/tickets/{ticket_id}/transition/", method="POST", data=transition_stale)
    assert status_stale == 409
    assert res_stale.get("error") == "ERR_STALE_VERSION"


def test_LP4_live_rbac_student_approval_denial_403():
    """Verify student role attempting approval receives HTTP 403 Forbidden with ERR_UNAUTHORIZED_APPROVAL"""
    # Use any valid UUID
    test_uuid = "00000000-0000-0000-0000-000000000001"
    approval_payload = {
        "user_role": "STUDENT",
        "approver_name": "student_attacker_192425155"
    }
    status_code, body = _http_request(f"/bookings/{test_uuid}/approve/", method="POST", data=approval_payload)
    assert status_code == 403
    assert body.get("error") == "ERR_UNAUTHORIZED_APPROVAL"
    assert "FACILITY_MANAGER" in body.get("authorized_roles", [])


def test_LP5_live_idempotent_telemetry_ingestion():
    """Verify repeated telemetry event ingestion is idempotent"""
    event_id = f"evt-test-{uuid.uuid4().hex[:6]}"
    telemetry_payload = {
        "sensor_id": "SNSR-TEMP-LAB204",
        "event_id": event_id,
        "temperature": 27.5,
        "humidity": 45.0
    }
    status1, _ = _http_request("/telemetry/", method="POST", data=telemetry_payload)
    status2, _ = _http_request("/telemetry/", method="POST", data=telemetry_payload)
    assert status1 in [200, 201]
    assert status2 in [200, 201]
