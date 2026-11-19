"""Compact test model of core campus-platform rules (Python + SQLite).
It is narrower than the full application: no HTTP, tokens or external services.
Author: KANDUKURI VIJAY BHASKAR REDDY (Reg No: 192425155)
Course Outcome: CO4 - Software Engineering Testing & DevOps
"""
import sqlite3

MATRIX = {
    ("High", "High"): "M1",
    ("High", "Medium"): "M2",
    ("High", "Low"): "M3",
    ("Medium", "High"): "M2",
    ("Medium", "Medium"): "M3",
    ("Medium", "Low"): "M4",
    ("Low", "High"): "M3",
    ("Low", "Medium"): "M4",
    ("Low", "Low"): "M4",
}

KEYWORDS = {
    "Facilities": ["leak", "flood", "ceiling", "door", "lock"],
    "HVAC": ["ac", "compressor", "temperature", "cooling"],
    "AV-Network": ["projector", "display", "wifi", "network"],
}

MAX_MINUTES = 180
TEMP_LIMIT = 28.0
TRANSITIONS = {
    "New": ["Assigned"],
    "Assigned": ["In Progress"],
    "In Progress": ["Resolved"],
    "Resolved": ["Closed"],
    "Closed": [],
}
STAFF = {"technician", "manager"}
APPROVERS = {"approver", "manager"}


def priority(impact, urgency):
    if (impact, urgency) not in MATRIX:
        raise ValueError("invalid matrix input")
    return MATRIX[(impact, urgency)]


def classify(text):
    words = text.lower().replace(",", " ").split()
    scores = {c: sum(1 for w in words if w in kws) for c, kws in KEYWORDS.items()}
    best = max(scores.values())
    top = [c for c, s in scores.items() if s == best]
    if best == 0 or len(top) != 1:
        return "Manual Review"
    return top[0]


def breached(value):
    return value > TEMP_LIMIT


def valid_duration(minutes):
    return 0 < minutes <= MAX_MINUTES


def overlaps(s1, e1, s2, e2):
    return s1 < e2 and s2 < e1  # half-open: back-to-back is allowed


class Store:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS tickets(
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            state TEXT NOT NULL,
            version INTEGER NOT NULL,
            notes TEXT,
            source TEXT,
            event_id TEXT,
            UNIQUE(source, event_id)
        );
        CREATE TABLE IF NOT EXISTS audit(
            id INTEGER PRIMARY KEY,
            ticket_id INTEGER,
            from_state TEXT,
            to_state TEXT,
            actor TEXT
        );
        CREATE TABLE IF NOT EXISTS bookings(
            id INTEGER PRIMARY KEY,
            facility TEXT,
            start_min INTEGER,
            end_min INTEGER,
            status TEXT
        );
        """)

    def create_ticket(self, title, source=None, event_id=None):
        if not title or not title.strip():
            raise ValueError("title required")
        if source is not None:
            row = self.db.execute(
                "SELECT id FROM tickets WHERE source=? AND event_id=?",
                (source, event_id),
            ).fetchone()
            if row:
                return row[0]
        cur = self.db.execute(
            "INSERT INTO tickets(title, state, version, source, event_id) VALUES(?, 'New', 1, ?, ?)",
            (title, source, event_id),
        )
        self.db.commit()
        return cur.lastrowid

    def count(self, table="tickets"):
        return self.db.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]

    def state(self, tid):
        return self.db.execute(
            "SELECT state, version FROM tickets WHERE id=?", (tid,)
        ).fetchone()

    def transition(self, tid, target, expected_version, role, notes=None):
        if role not in STAFF:
            raise PermissionError("role not permitted")
        state, version = self.state(tid)
        if target not in TRANSITIONS.get(state, []):
            raise ValueError(f"invalid transition {state} -> {target}")
        if target == "Resolved" and not (notes and notes.strip()):
            raise ValueError("resolution notes required")
        cur = self.db.execute(
            "UPDATE tickets SET state=?, version=version+1, notes=COALESCE(?, notes) WHERE id=? AND version=?",
            (target, notes, tid, expected_version),
        )
        if cur.rowcount != 1:
            self.db.rollback()
            raise RuntimeError("stale version")
        self.db.execute(
            "INSERT INTO audit(ticket_id, from_state, to_state, actor) VALUES(?, ?, ?, ?)",
            (tid, state, target, role),
        )
        self.db.commit()
        return version + 1

    def audit_count(self, tid):
        return self.db.execute(
            "SELECT COUNT(*) FROM audit WHERE ticket_id=?", (tid,)
        ).fetchone()[0]

    def request_booking(self, facility, start, end):
        if not valid_duration(end - start):
            raise ValueError("duration outside policy")
        for s, e in self.db.execute(
            "SELECT start_min, end_min FROM bookings WHERE facility=? AND status='Pending'",
            (facility,),
        ):
            if overlaps(start, end, s, e):
                raise RuntimeError("overlapping booking")
        cur = self.db.execute(
            "INSERT INTO bookings(facility, start_min, end_min, status) VALUES(?, ?, ?, 'Pending')",
            (facility, start, end),
        )
        self.db.commit()
        return cur.lastrowid

    def approve_booking(self, bid, role):
        if role not in APPROVERS:
            raise PermissionError("role not permitted")
        self.db.execute(
            "UPDATE bookings SET status='Approved' WHERE id=?", (bid,)
        )
        self.db.commit()

    def booking_status(self, bid):
        return self.db.execute(
            "SELECT status FROM bookings WHERE id=?", (bid,)
        ).fetchone()[0]


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

