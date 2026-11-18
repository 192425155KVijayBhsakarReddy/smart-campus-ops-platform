"""Test 1: Real Concurrency Race Test against Nginx & PostgreSQL 16
Fires 10 concurrent threads attempting to book the exact same room & time slot.
Validates that PostgreSQL 16 btree_gist ExclusionConstraint permits exactly 1 booking
and rejects 9 concurrent requests with HTTP 409 Conflict.
"""
import requests
import threading
import time
import json

NGINX_URL = "http://localhost/api/bookings/"

ROOM = "LAB-201"
START_TIME = "2026-11-20T10:00:00Z"
END_TIME = "2026-11-20T12:00:00Z"

results = []
lock = threading.Lock()

def book_slot(thread_id):
    payload = {
        "room": ROOM,
        "start_time": START_TIME,
        "end_time": END_TIME,
        "booked_by": f"Researcher_{thread_id}",
        "user_role": "FACULTY",
        "purpose": f"Concurrent Race Evaluation Thread {thread_id}",
        "status": "CONFIRMED"
    }
    t0 = time.perf_counter()
    try:
        resp = requests.post(NGINX_URL, json=payload, timeout=5)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        with lock:
            results.append({
                "thread_id": thread_id,
                "status_code": resp.status_code,
                "latency_ms": round(dt_ms, 2),
                "data": resp.json()
            })
    except Exception as exc:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        with lock:
            results.append({
                "thread_id": thread_id,
                "status_code": 500,
                "latency_ms": round(dt_ms, 2),
                "error": str(exc)
            })

def run_race():
    print("=" * 80)
    print("EXECUTING REAL POSTGRESQL 16 CONCURRENCY RACE VIA NGINX CLUSTER")
    print(f"Target: {NGINX_URL} | Room: {ROOM} | Interval: {START_TIME} -> {END_TIME}")
    print("=" * 80)

    threads = [threading.Thread(target=book_slot, args=(i+1,)) for i in range(10)]
    t_start = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    t_total = (time.perf_counter() - t_start) * 1000.0

    print(f"\nCompleted 10 concurrent requests in {t_total:.2f} ms.\n")
    print(f"{'Thread':<8} | {'Status Code':<12} | {'Latency':<10} | {'Outcome & Detail'}")
    print("-" * 80)

    success_count = 0
    conflict_count = 0

    for r in sorted(results, key=lambda x: x["latency_ms"]):
        tid = f"T-{r['thread_id']}"
        sc = r["status_code"]
        lat = f"{r['latency_ms']} ms"
        if sc == 201:
            success_count += 1
            ref = r["data"].get("booking_reference", "N/A")
            node = r["data"].get("node_hostname", "N/A")
            detail = f"SUCCESS (HTTP 201) -> Ref: {ref} [Served by: {node}]"
        elif sc == 409:
            conflict_count += 1
            err = r["data"].get("error", "ERR_SLOT_OVERLAP")
            node = r["data"].get("node_hostname", "N/A")
            detail = f"CONFLICT (HTTP 409) -> {err}: {r['data'].get('engine_rejection', '')} [Node: {node}]"
        else:
            detail = f"ERROR: {r.get('error', r.get('data'))}"
        print(f"{tid:<8} | {sc:<12} | {lat:<10} | {detail}")

    print("=" * 80)
    print(f"VERIFICATION SUMMARY: Exactly {success_count} Confirmed Booking, {conflict_count} Rejections.")
    if success_count == 1 and conflict_count == 9:
        print("RESULT: 100% INVARIANT PASS! PostgreSQL 16 btree_gist exclusion constraint prevented double-booking.")
    else:
        print("RESULT: INVARIANT VIOLATION DETECTED.")
    print("=" * 80)

if __name__ == '__main__':
    run_race()
