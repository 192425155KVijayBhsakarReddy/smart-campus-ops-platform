# SMART CAMPUS FACILITY BOOKING & MAINTENANCE PLATFORM
## Turnkey Full-Stack Real Implementation Guide (Assignment 3 - CO3)
**Author:** KANDUKURI VIJAY BHASKAR REDDY (Reg No: 192425155)  
**Course:** CSA10 - Software Engineering  

This directory contains the **real, production-grade codebase** answering all faculty feedback for Assignment 3:
- **Backend:** Django 4.2 + Django REST Framework with native PostgreSQL 16 `btree_gist` ExclusionConstraint on booking intervals (`[start, end)`), optimistic version locking on maintenance tickets, and idempotent sensor ingestion.
- **Dual Replicas:** `backend-1` and `backend-2` running independently behind Nginx.
- **Frontend:** Vue 3 reactive Single-Page Application (SPA) displaying the Calendar with interactive 409 Conflict modal, M1–M4 Triage Queue, IoT Telemetry Dial, and Dual-Control Change Approval Modal.
- **Proxy:** Nginx upstream cluster load-balancing between dual backends on port 80.
- **Database:** PostgreSQL 16 with persistent volume `pgdata`. Celery has been completely removed.

---

## Quick Step-by-Step Execution Instructions

### Step 1: Start Docker Desktop
1. Open **Docker Desktop** from your Windows Start Menu.
2. Wait until the whale icon in the taskbar turns solid green (Docker Engine running).

### Step 2: Build & Start the Multi-Container Stack
Open PowerShell, navigate to this folder, and run:
```powershell
cd S:\SE\Assignments\Original_Templates_Backup\smart_campus_platform
docker compose up --build -d
```
*Wait ~45 seconds while PostgreSQL initializes, extensions are loaded, migrations run, and initial rooms/tickets are seeded.*

Verify all 5 containers are running and healthy:
```powershell
docker compose ps
```
*(Take a screenshot or copy the terminal output for Task 5!)*

---

### Step 3: Access the Live Application & Capture UI Evidence (Task 3)
Open your web browser and navigate to: **`http://localhost/`**

1. **Screenshot 1 — Booking Calendar & HTTP 409 Conflict Modal:**
   - In Tab 1 (*Facility Booking Calendar*), click the red button: **"Trigger 409 Conflict Simulation (Same Room & Time)"**.
   - The real PostgreSQL 16 `btree_gist` exclusion constraint will reject the overlapping interval and pop up the **"HTTP 409 CONFLICT: SLOT OVERLAP REJECTED"** modal.
   - *Capture a screenshot of this modal with its database driver trace.*

2. **Screenshot 2 — Unified Maintenance Queue (M1–M4 Triage):**
   - Click Tab 2 (*Unified Maintenance Queue*).
   - Shows the live triage table with priority tags (`M1`, `M2`, `M3`), status pills, and optimistic version tags (`v7`, `v2`).
   - *Capture a screenshot of this table.*

3. **Screenshot 3 — Controlled IoT Sensor Telemetry Ingest:**
   - Click Tab 3 (*IoT Sensor Telemetry Ingest*).
   - Click **"Trigger Critical Breach (38.5°C)"** to demonstrate real-time threshold alerting (> 28.0°C) and automatic generation of an M1 emergency maintenance ticket.
   - Click **"Replay Duplicate Packet (5x Storm)"** to demonstrate idempotent deduplication.
   - *Capture a screenshot of the telemetry feed.*

4. **Screenshot 4 — Dual-Control Operational Change Approval Modal:**
   - Click Tab 4 (*Dual-Control Change Approval Modal*).
   - Select role: **"Student"**, then click **"Authorize Reservation"** &rarr; displays the real **HTTP 403 Forbidden Access Denied** rejection!
   - Change role to **"Facility Manager"** &rarr; displays successful **HTTP 200 OK** authorization!
   - *Capture a screenshot of this card.*

---

### Step 4: Execute Real Concurrency Race & Failover Scripts (Task 6)
Open PowerShell in the `smart_campus_platform` directory and run:

1. **Real PostgreSQL 16 Exclusion Race Test:**
   ```powershell
   python tests/test_concurrency_race.py
   ```
   *Fires 10 concurrent threads to Nginx. Shows exactly 1 thread succeeding (HTTP 201) and 9 threads rejected with HTTP 409 Conflict by PostgreSQL's `exclude_overlapping_bookings` constraint.*

2. **Dynamic Replica Restart & Failover Test:**
   ```powershell
   python tests/test_failover_load.py
   ```
   *Pours continuous traffic through Nginx while executing `docker compose restart backend-1`. Verifies 100% routing to `backend-2` with zero 502/503 dropped requests.*

3. **Optimistic Locking Reflection Test (Task 7 Reflection Item 2):**
   ```powershell
   python tests/test_optimistic_locking.py
   ```
   *Formally proves that without the version column, Tech Bob silently overwrites Tech Sarah's resolution (Lost Update bug), while with the version column, Bob's stale update is rejected with HTTP 409 Conflict.*

---

### Step 5: Capture Git Log & Conflict Evidence (Task 4)
Run:
```powershell
.\setup_git_workflow.bat
```
Then run:
```powershell
git log --graph --oneline --all
```
And check `config/policies.json` to see the conflict resolution between PostgreSQL GiST exclusion and Redis locking.

---

### Step 6: Shutdown When Done
```powershell
docker compose down
```
*(The named volume `pgdata` retains all database state for persistent restarts).*
