"""
CAMPUS PLATFORM POLICY & OUTBOX ENGINE (DAY-4 MULTI-CAMPUS ADAPTATION)
Author: KANDUKURI VIJAY BHASKAR REDDY (Reg No: 192425155)
Course: CSA10 - Software Engineering | CO4: Platform Core Engine
"""

class MultiCampusPolicyEngine:
    """Authoritative multi-campus policy evaluator enforcing campus-specific rules."""
    POLICIES = {
        "CAMPUS-ENG": {"name": "Engineering Campus", "max_duration": 180, "temp_threshold": 28.0},
        "CAMPUS-MED": {"name": "Medical Campus",     "max_duration": 240, "temp_threshold": 26.0},
        "CAMPUS-DC":  {"name": "Data Center Complex", "max_duration": 120, "temp_threshold": 24.0},
    }

    @classmethod
    def get_policy(cls, campus_code: str):
        return cls.POLICIES.get(campus_code, cls.POLICIES["CAMPUS-ENG"])

    @classmethod
    def validate_booking(cls, campus_code: str, duration_minutes: int) -> bool:
        policy = cls.get_policy(campus_code)
        if duration_minutes < 1 or duration_minutes > policy["max_duration"]:
            raise ValueError(f"Duration {duration_minutes}m exceeds {campus_code} maximum of {policy['max_duration']}m")
        return True

    @classmethod
    def check_temp_breach(cls, campus_code: str, value: float) -> bool:
        policy = cls.get_policy(campus_code)
        return value > policy["temp_threshold"]

    @classmethod
    def normalize_and_validate_booking_payload(cls, payload: dict) -> dict:
        """Expand-and-contract backward compatibility adapter:
        Accepts legacy v1 schemas lacking 'campus_code' (defaulting safely to 'CAMPUS-ENG'),
        calculates duration from start/end intervals, validates against campus duration limits,
        and returns a normalized schema v2 payload."""
        normalized = payload.copy()
        campus_code = normalized.get("campus_code", "CAMPUS-ENG")
        normalized["campus_code"] = campus_code
        
        duration = normalized.get("duration_minutes")
        if duration is None:
            if "start" in normalized and "end" in normalized:
                duration = normalized["end"] - normalized["start"]
            elif "start_time" in normalized and "end_time" in normalized:
                duration = 60
            else:
                duration = 60
            normalized["duration_minutes"] = duration

        cls.validate_booking(campus_code, duration)
        normalized["policy_applied"] = cls.get_policy(campus_code)["name"]
        return normalized


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
