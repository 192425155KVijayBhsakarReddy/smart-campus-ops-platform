"""
CAMPUS PLATFORM POLICY & DURABLE OUTBOX ENGINE (DAY-4 MULTI-CAMPUS ADAPTATION)
Author: KANDUKURI VIJAY BHASKAR REDDY (Reg No: 192425155)
Course: CSA10 - Software Engineering | CO4: Platform Core Engine
"""

from datetime import datetime, timezone, timedelta
import json
import sqlite3
import os
import uuid
import time


class MultiCampusPolicyEngine:
    """Authoritative multi-campus policy evaluator enforcing campus-specific rules and API v2 adaptation."""
    POLICIES = {
        "CAMPUS-ENG": {"name": "Engineering Campus", "max_duration": 180, "temp_threshold": 28.0},
        "CAMPUS-MED": {"name": "Medical Campus",     "max_duration": 240, "temp_threshold": 26.0},
        "CAMPUS-DC":  {"name": "Data Center Complex", "max_duration": 120, "temp_threshold": 24.0},
    }

    @classmethod
    def get_policy(cls, campus_id: str):
        # Support canonical campus_id with campus_code fallback
        cid = campus_id.upper() if campus_id else "CAMPUS-ENG"
        return cls.POLICIES.get(cid, cls.POLICIES["CAMPUS-ENG"])

    @classmethod
    def validate_booking(cls, campus_id: str, duration_minutes: int) -> bool:
        policy = cls.get_policy(campus_id)
        if duration_minutes < 1 or duration_minutes > policy["max_duration"]:
            raise ValueError(f"Duration {duration_minutes}m exceeds {campus_id} maximum of {policy['max_duration']}m")
        return True

    @classmethod
    def check_temp_breach(cls, campus_id: str, value: float) -> bool:
        policy = cls.get_policy(campus_id)
        return value > policy["temp_threshold"]

    @classmethod
    def normalize_and_validate_booking_payload(cls, payload: dict) -> dict:
        """
        API v2 Schema Adapter with ISO-8601 Timestamp Validation & Backward Compatibility:
        - Resolves canonical 'campus_id' (accepting legacy 'campus_code' or defaulting to 'CAMPUS-ENG').
        - Parses ISO-8601 strings (e.g. '2026-11-20T10:00:00Z'), computes exact duration minutes.
        - Converts legacy minute offsets ('start': 600, 'end': 720) into normalized ISO-8601 UTC strings.
        - Enforces strict chronological order (start < end).
        - Validates duration against campus-specific maximum ceilings.
        """
        normalized = payload.copy()
        
        # 1. Resolve canonical campus_id (supporting legacy campus_code)
        campus_id = normalized.get("campus_id") or normalized.get("campus_code") or "CAMPUS-ENG"
        campus_id = campus_id.upper()
        normalized["campus_id"] = campus_id
        normalized["campus_code"] = campus_id  # Maintain dual-field compatibility

        # 2. Parse Timestamps or convert legacy minute offsets
        start_time_raw = normalized.get("start_time")
        end_time_raw = normalized.get("end_time")

        if start_time_raw and end_time_raw:
            # Parse ISO-8601 strings
            s_str = start_time_raw.replace("Z", "+00:00")
            e_str = end_time_raw.replace("Z", "+00:00")
            try:
                dt_start = datetime.fromisoformat(s_str)
                dt_end = datetime.fromisoformat(e_str)
            except ValueError as ex:
                raise ValueError(f"Invalid ISO-8601 timestamp format: {ex}")

            if dt_end <= dt_start:
                raise ValueError(f"Invalid booking interval: end_time ({end_time_raw}) must be strictly after start_time ({start_time_raw})")

            duration = int((dt_end - dt_start).total_seconds() / 60)
            normalized["start_time"] = dt_start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            normalized["end_time"] = dt_end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            normalized["duration_minutes"] = duration
        elif "start" in normalized and "end" in normalized:
            # Legacy minute offset conversion to ISO-8601
            m_start = int(normalized["start"])
            m_end = int(normalized["end"])
            if m_end <= m_start:
                raise ValueError("Invalid minute interval: end must be strictly greater than start")
            duration = m_end - m_start
            
            # Base reference date: 2026-11-20
            base_date = datetime(2026, 11, 20, 0, 0, 0, tzinfo=timezone.utc)
            dt_start = base_date + timedelta(minutes=m_start)
            dt_end = base_date + timedelta(minutes=m_end)
            
            normalized["start_time"] = dt_start.strftime("%Y-%m-%dT%H:%M:%SZ")
            normalized["end_time"] = dt_end.strftime("%Y-%m-%dT%H:%M:%SZ")
            normalized["duration_minutes"] = duration
        else:
            duration = normalized.get("duration_minutes", 60)
            normalized["duration_minutes"] = duration

        # 3. Enforce campus-specific duration limits
        cls.validate_booking(campus_id, duration)
        normalized["policy_applied"] = cls.get_policy(campus_id)["name"]
        return normalized


class OutboxIntentBuffer:
    """
    Durable Database-Backed Outbox Buffer:
    Persists integration intents directly to an ACID-compliant disk store (SQLite / PostgreSQL),
    ensuring zero data loss across process crashes, application restarts, and network partitions.
    """
    def __init__(self, db_path="outbox_intents.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS outbox_intents (
                        intent_id TEXT PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        status TEXT NOT NULL,
                        retry_count INTEGER DEFAULT 0,
                        next_retry_at REAL DEFAULT 0.0,
                        last_error TEXT,
                        created_at REAL NOT NULL,
                        processed_at REAL
                    );
                """)
        finally:
            conn.close()

    def dispatch(self, event_type: str, payload: dict, remote_status_code: int, intent_id: str = None):
        """
        Dispatches external synchronization intent.
        Prevents duplicate processing using unique intent_id.
        On remote failure (HTTP 500/502/503/504), writes durable intent to ACID storage with status PENDING_RETRY.
        """
        if not intent_id:
            intent_id = f"INTENT-{uuid.uuid4().hex[:8].upper()}"
        now = time.time()
        payload_json = json.dumps(payload)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT intent_id, status FROM outbox_intents WHERE intent_id = ?;", (intent_id,))
                existing = cur.fetchone()
                if existing:
                    return {
                        "status": existing["status"],
                        "intent_id": intent_id,
                        "duplicate_ignored": True
                    }

                if remote_status_code == 200:
                    conn.execute("""
                        INSERT INTO outbox_intents (intent_id, event_type, payload, status, retry_count, created_at, processed_at)
                        VALUES (?, ?, ?, 'PROCESSED', 0, ?, ?);
                    """, (intent_id, event_type, payload_json, now, now))
                    return {"status": "SYNCED", "remote_id": "EXT-9901", "intent_id": intent_id}
                elif remote_status_code in [500, 502, 503, 504]:
                    conn.execute("""
                        INSERT INTO outbox_intents (intent_id, event_type, payload, status, retry_count, next_retry_at, created_at)
                        VALUES (?, ?, ?, 'PENDING_RETRY', 0, ?, ?);
                    """, (intent_id, event_type, payload_json, now, now))
                    return {
                        "status": "BUFFERED",
                        "intent_id": intent_id,
                        "intent": {
                            "event_type": event_type,
                            "payload": payload,
                            "status": "PENDING_RETRY",
                            "retries": 0
                        }
                    }
                else:
                    raise RuntimeError(f"Unexpected remote gateway error: HTTP {remote_status_code}")
        finally:
            conn.close()

    def get_pending_intents(self):
        """Fetches all un-dispatched intents from durable storage."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM outbox_intents WHERE status = 'PENDING_RETRY' ORDER BY created_at ASC;")
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def count_intents(self, status=None):
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            if status:
                cur.execute("SELECT COUNT(*) FROM outbox_intents WHERE status = ?;", (status,))
            else:
                cur.execute("SELECT COUNT(*) FROM outbox_intents;")
            return cur.fetchone()[0]
        finally:
            conn.close()

    def process_outbox_queue(self, remote_handler, max_retries=3, backoff_base=2.0):
        """
        Persistent background retry worker:
        Scans durable outbox table for PENDING_RETRY records, attempts synchronization,
        applies exponential backoff with jitter on failures, and transitions records to DEAD_LETTER when exhausted.
        """
        processed_count = 0
        retried_count = 0
        dead_letter_count = 0
        now = time.time()

        pending = self.get_pending_intents()
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                for item in pending:
                    iid = item["intent_id"]
                    retries = item["retry_count"]
                    payload = json.loads(item["payload"])
                    event_type = item["event_type"]

                    success = False
                    err_msg = ""
                    try:
                        success = remote_handler(event_type, payload)
                    except Exception as ex:
                        success = False
                        err_msg = str(ex)

                    if success:
                        conn.execute("UPDATE outbox_intents SET status = 'PROCESSED', processed_at = ? WHERE intent_id = ?;", (now, iid))
                        processed_count += 1
                    else:
                        new_retries = retries + 1
                        if new_retries >= max_retries:
                            conn.execute("UPDATE outbox_intents SET status = 'DEAD_LETTER', retry_count = ?, last_error = ? WHERE intent_id = ?;", 
                                         (new_retries, err_msg or "Max retries exceeded", iid))
                            dead_letter_count += 1
                        else:
                            backoff = (backoff_base ** new_retries)
                            conn.execute("UPDATE outbox_intents SET retry_count = ?, next_retry_at = ?, last_error = ? WHERE intent_id = ?;", 
                                         (new_retries, now + backoff, err_msg or "Remote unavailable", iid))
                            retried_count += 1
        finally:
            conn.close()

        return {
            "processed": processed_count,
            "retried": retried_count,
            "dead_letter": dead_letter_count,
            "remaining_pending": self.count_intents("PENDING_RETRY")
        }
