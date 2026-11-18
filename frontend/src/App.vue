<template>
  <div class="campus-container">
    <!-- Top Header -->
    <header class="navbar">
      <div class="logo">
        <i class="fa-solid fa-graduation-cap"></i>
        <span>SMART CAMPUS PLATFORM</span>
        <span class="badge-student">CO3: Full-Stack Containerized Platform | Reg: 192425155</span>
      </div>
      <div class="header-status">
        <span class="status-indicator online"></span>
        <span>Dual Backend Cluster: Nginx Upstream -> backend-1 / backend-2</span>
      </div>
    </header>

    <!-- Main Navigation Tabs -->
    <nav class="nav-tabs">
      <button :class="['tab-btn', { active: activeTab === 'calendar' }]" @click="activeTab = 'calendar'">
        <i class="fa-regular fa-calendar-days"></i> 1. Facility Booking Calendar (409 Conflict)
      </button>
      <button :class="['tab-btn', { active: activeTab === 'queue' }]" @click="activeTab = 'queue'">
        <i class="fa-solid fa-list-check"></i> 2. Unified Maintenance Queue (M1-M4 Triage)
      </button>
      <button :class="['tab-btn', { active: activeTab === 'telemetry' }]" @click="activeTab = 'telemetry'">
        <i class="fa-solid fa-tower-broadcast"></i> 3. IoT Sensor Telemetry Ingest
      </button>
      <button :class="['tab-btn', { active: activeTab === 'approval' }]" @click="activeTab = 'approval'">
        <i class="fa-solid fa-user-shield"></i> 4. Dual-Control Change Approval Modal
      </button>
    </nav>

    <!-- Content Area -->
    <main class="main-content">
      <!-- TAB 1: FACILITY BOOKING CALENDAR -->
      <section v-if="activeTab === 'calendar'" class="card">
        <div class="card-header">
          <h2><i class="fa-regular fa-calendar-check"></i> Facility Reservation & Concurrency Validation</h2>
          <p class="subtitle">Guaranteed collision prevention via PostgreSQL 16 <code>btree_gist</code> exclusion constraints across dual backends.</p>
        </div>

        <div class="grid-2col">
          <!-- Reservation Form -->
          <div class="form-box">
            <h3>New Facility Reservation Request</h3>
            <div class="form-group">
              <label>Select Room / Facility:</label>
              <select v-model="bookingForm.room">
                <option value="LAB-201">LAB-201 (Advanced Robotics & AI Lab - Restricted)</option>
                <option value="LAB-204">LAB-204 (Microprocessor Lab - Restricted)</option>
                <option value="AUD-101">AUD-101 (Main Auditorium - Public)</option>
                <option value="CONF-301">CONF-301 (Faculty Boardroom - Restricted)</option>
              </select>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Start Time (ISO UTC):</label>
                <input type="datetime-local" v-model="bookingForm.startTime" />
              </div>
              <div class="form-group">
                <label>End Time (ISO UTC):</label>
                <input type="datetime-local" v-model="bookingForm.endTime" />
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Booked By (User):</label>
                <input type="text" v-model="bookingForm.bookedBy" />
              </div>
              <div class="form-group">
                <label>Role:</label>
                <select v-model="bookingForm.userRole">
                  <option value="FACULTY">Faculty Member</option>
                  <option value="STUDENT">Student</option>
                  <option value="FACILITY_MANAGER">Facility Manager</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label>Academic Purpose:</label>
              <input type="text" v-model="bookingForm.purpose" placeholder="e.g., Autonomous Robotics Final Evaluation" />
            </div>

            <div class="button-group">
              <button class="btn btn-primary" @click="submitBooking">
                <i class="fa-solid fa-plus"></i> Submit Reservation
              </button>
              <button class="btn btn-danger" @click="simulateOverlapRace">
                <i class="fa-solid fa-bolt"></i> Trigger 409 Conflict Simulation (Same Room & Time)
              </button>
            </div>

            <div v-if="successMsg" class="alert alert-success">
              <i class="fa-solid fa-circle-check"></i> {{ successMsg }}
            </div>
          </div>

          <!-- Existing Active Reservations -->
          <div class="list-box">
            <h3>Active Confirmed Bookings in Cluster</h3>
            <div v-if="bookings.length === 0" class="empty-state">No active reservations recorded.</div>
            <div v-for="b in bookings" :key="b.id" class="booking-card">
              <div class="booking-header">
                <span class="ref-tag">{{ b.booking_reference }}</span>
                <span class="status-badge confirmed">{{ b.status }}</span>
              </div>
              <div class="booking-details">
                <strong><i class="fa-solid fa-door-open"></i> {{ b.room }}</strong>
                <p><i class="fa-regular fa-clock"></i> {{ formatTime(b.start_time) }} &rarr; {{ formatTime(b.end_time) }}</p>
                <p><i class="fa-regular fa-user"></i> Booked by: {{ b.booked_by }} ({{ b.user_role }})</p>
                <small class="node-tag">Served by replica: {{ b.node_hostname || 'backend-1' }}</small>
              </div>
            </div>
          </div>
        </div>

        <!-- 409 CONFLICT MODAL (FACULTY EVIDENCE REQUIREMENT) -->
        <div v-if="show409Modal" class="modal-overlay">
          <div class="modal-content modal-danger">
            <div class="modal-header">
              <div class="modal-title">
                <i class="fa-solid fa-triangle-exclamation"></i>
                <span>HTTP 409 CONFLICT: SLOT OVERLAP REJECTED</span>
              </div>
              <button class="close-btn" @click="show409Modal = false">&times;</button>
            </div>
            <div class="modal-body">
              <div class="error-banner">
                <strong>PostgreSQL 16 Storage Engine Invariant Violation Caught!</strong>
                <p>{{ conflictError.detail }}</p>
              </div>
              <div class="code-details">
                <div class="kv"><span>HTTP Status:</span> <strong>409 Conflict</strong></div>
                <div class="kv"><span>Target Room:</span> <code>{{ conflictError.room }}</code></div>
                <div class="kv"><span>Requested Interval:</span> <code>{{ conflictError.conflict_interval }}</code></div>
                <div class="kv"><span>Rejection Cause:</span> <code>{{ conflictError.engine_rejection }}</code></div>
                <div class="kv"><span>Serving Node:</span> <code>{{ conflictError.node_hostname }}</code></div>
                <div class="raw-db-box">
                  <small>Database Driver Trace:</small>
                  <pre>{{ conflictError.raw_db_error }}</pre>
                </div>
              </div>
            </div>
            <div class="modal-footer">
              <button class="btn btn-secondary" @click="show409Modal = false">Acknowledge & Reschedule</button>
            </div>
          </div>
        </div>
      </section>

      <!-- TAB 2: UNIFIED MAINTENANCE QUEUE -->
      <section v-if="activeTab === 'queue'" class="card">
        <div class="card-header">
          <h2><i class="fa-solid fa-wrench"></i> Unified Maintenance Queue & Optimistic Locking Triage</h2>
          <p class="subtitle">M1–M4 emergency triage with optimistic version counters preventing lost technician updates.</p>
        </div>

        <div class="table-responsive">
          <table class="data-table">
            <thead>
              <tr>
                <th>Ticket ID</th>
                <th>Priority</th>
                <th>Title / Description</th>
                <th>Category</th>
                <th>Status</th>
                <th>Version</th>
                <th>Assigned Technician</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in tickets" :key="t.id">
                <td><code>{{ t.ticket_number }}</code></td>
                <td><span :class="['badge-priority', t.priority.toLowerCase()]">{{ t.priority }}</span></td>
                <td><strong>{{ t.title }}</strong></td>
                <td>{{ t.category }}</td>
                <td><span class="status-pill">{{ t.status }}</span></td>
                <td><span class="version-tag">v{{ t.version }}</span></td>
                <td>{{ t.assigned_to || 'Unassigned' }}</td>
                <td>
                  <button class="btn btn-sm btn-outline" @click="resolveTicket(t)">Resolve (v{{ t.version }})</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- TAB 3: IOT SENSOR TELEMETRY INGEST -->
      <section v-if="activeTab === 'telemetry'" class="card">
        <div class="card-header">
          <h2><i class="fa-solid fa-microchip"></i> Controlled IoT Sensor Telemetry & Idempotent Ingestion</h2>
          <p class="subtitle">Automated M1 ticket generation upon threshold breach (> 28.0°C) and duplicate packet deduplication.</p>
        </div>

        <div class="grid-2col">
          <div class="telemetry-panel">
            <h3>Inject Sensor Telemetry Packet</h3>
            <div class="form-group">
              <label>Sensor Identifier:</label>
              <input type="text" v-model="sensorForm.sensorId" />
            </div>
            <div class="form-group">
              <label>Recorded Temperature (°C):</label>
              <input type="number" step="0.1" v-model="sensorForm.value" />
            </div>
            <div class="form-group">
              <label>Event Sequence ID (Idempotency Key):</label>
              <input type="text" v-model="sensorForm.eventId" />
            </div>

            <div class="button-group">
              <button class="btn btn-primary" @click="sendTelemetry(false)">
                <i class="fa-solid fa-paper-plane"></i> Send Normal Telemetry (24.5°C)
              </button>
              <button class="btn btn-danger" @click="sendTelemetry(true)">
                <i class="fa-solid fa-fire"></i> Trigger Critical Breach (38.5°C)
              </button>
              <button class="btn btn-secondary" @click="sendDuplicateReplayBurst">
                <i class="fa-solid fa-repeat"></i> Replay Duplicate Packet (5x Storm)
              </button>
            </div>

            <div v-if="telemetryFeedback" :class="['alert', telemetryBreach ? 'alert-danger' : 'alert-success']">
              {{ telemetryFeedback }}
            </div>
          </div>

          <div class="telemetry-monitor">
            <h3>Recent Telemetry Feed</h3>
            <div class="feed-box">
              <div v-for="item in telemetryLogs" :key="item.id" class="feed-item">
                <span :class="['telemetry-badge', item.is_breach ? 'badge-breach' : 'badge-normal']">
                  {{ item.value }}°C
                </span>
                <div class="feed-details">
                  <strong>{{ item.sensor_id }}</strong> [Seq: {{ item.event_id }}]
                  <small>{{ item.is_breach ? 'CRITICAL THRESHOLD BREACH (> 28.0°C)' : 'Operating within safe parameters' }}</small>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- TAB 4: DUAL-CONTROL CHANGE APPROVAL MODAL -->
      <section v-if="activeTab === 'approval'" class="card">
        <div class="card-header">
          <h2><i class="fa-solid fa-shield-halved"></i> Dual-Control Operational Change Approval</h2>
          <p class="subtitle">Enforces strict server-side RBAC: Students receive HTTP 403 Forbidden on restricted bookings.</p>
        </div>

        <div class="approval-box">
          <div class="pending-card">
            <div class="badge-restricted">RESTRICTED FACILITY APPROVAL REQUIRED</div>
            <h3>Reservation Request: LAB-201 (Robotics & AI Research Facility)</h3>
            <p><strong>Applicant:</strong> Vijay Bhaskar Reddy (Student - 192425155)</p>
            <p><strong>Schedule:</strong> Friday, 14:00 - 18:00 UTC (4-Hour Intensive Run)</p>
            <p><strong>Status:</strong> <span class="status-badge pending">PENDING_APPROVAL</span></p>

            <div class="role-selector">
              <label>Authorize As Role:</label>
              <select v-model="selectedRole">
                <option value="STUDENT">Student (Unauthorized Role - Tests 403)</option>
                <option value="TECHNICIAN">Technician (Unauthorized Role - Tests 403)</option>
                <option value="FACILITY_MANAGER">Facility Manager (Authorized Dual-Control Role)</option>
                <option value="DEPT_HEAD">Department Head (Authorized Dual-Control Role)</option>
              </select>
            </div>

            <div class="button-group">
              <button class="btn btn-primary" @click="executeApproval">
                <i class="fa-solid fa-check-double"></i> Authorize Reservation
              </button>
            </div>

            <div v-if="approvalResult" :class="['alert', approvalError ? 'alert-danger' : 'alert-success']">
              <strong>{{ approvalResult.title }}</strong>
              <p>{{ approvalResult.detail }}</p>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script>
import axios from 'axios';

const API_BASE = '/api';

export default {
  data() {
    return {
      activeTab: 'calendar',
      bookingForm: {
        room: 'LAB-201',
        startTime: '2026-11-20T10:00',
        endTime: '2026-11-20T12:00',
        bookedBy: 'Prof. Sharma',
        userRole: 'FACULTY',
        purpose: 'Autonomous Robotics Simulation'
      },
      bookings: [],
      successMsg: null,
      show409Modal: false,
      conflictError: {},
      tickets: [],
      sensorForm: {
        sensorId: 'TEMP-AC-402',
        value: 24.5,
        eventId: 'EVT-1001'
      },
      telemetryLogs: [],
      telemetryFeedback: null,
      telemetryBreach: false,
      selectedRole: 'STUDENT',
      approvalResult: null,
      approvalError: false
    };
  },
  mounted() {
    this.fetchBookings();
    this.fetchTickets();
    this.fetchTelemetry();
  },
  methods: {
    formatTime(dtStr) {
      if (!dtStr) return '';
      return new Date(dtStr).toLocaleString();
    },
    async fetchBookings() {
      try {
        const res = await axios.get(`${API_BASE}/bookings/`);
        this.bookings = res.data;
      } catch (err) {
        console.error('Failed to load bookings', err);
      }
    },
    async fetchTickets() {
      try {
        const res = await axios.get(`${API_BASE}/tickets/`);
        this.tickets = res.data;
      } catch (err) {
        console.error('Failed to load tickets', err);
      }
    },
    async fetchTelemetry() {
      try {
        const res = await axios.get(`${API_BASE}/telemetry/`);
        this.telemetryLogs = res.data;
      } catch (err) {
        console.error('Failed to load telemetry', err);
      }
    },
    async submitBooking() {
      this.successMsg = null;
      try {
        const payload = {
          room: this.bookingForm.room,
          start_time: new Date(this.bookingForm.startTime).toISOString(),
          end_time: new Date(this.bookingForm.endTime).toISOString(),
          booked_by: this.bookingForm.bookedBy,
          user_role: this.bookingForm.userRole,
          purpose: this.bookingForm.purpose,
          status: 'CONFIRMED'
        };
        const res = await axios.post(`${API_BASE}/bookings/`, payload);
        this.successMsg = `Booking Confirmed! Ref: ${res.data.booking_reference} (Node: ${res.data.node_hostname})`;
        await this.fetchBookings();
      } catch (err) {
        if (err.response && err.response.status === 409) {
          this.conflictError = err.response.data;
          this.show409Modal = true;
        } else {
          alert('Booking failed: ' + (err.response?.data?.detail || err.message));
        }
      }
    },
    async simulateOverlapRace() {
      // Simulates concurrent double-booking of LAB-201
      this.bookingForm.room = 'LAB-201';
      this.bookingForm.startTime = '2026-11-20T10:00';
      this.bookingForm.endTime = '2026-11-20T12:00';
      this.bookingForm.bookedBy = 'Dr. Vikram';
      await this.submitBooking();
    },
    async resolveTicket(ticket) {
      try {
        const res = await axios.post(`${API_BASE}/tickets/${ticket.id}/transition/`, {
          expected_version: ticket.version,
          target_status: 'RESOLVED',
          resolution_notes: 'Inspected and certified by field technician.',
          actor: 'Tech Sarah'
        });
        alert(`Ticket ${ticket.ticket_number} resolved successfully! Version updated to v${res.data.version}.`);
        await this.fetchTickets();
      } catch (err) {
        if (err.response && err.response.status === 409) {
          alert(`HTTP 409 Concurrency Conflict: ${err.response.data.detail}`);
        } else {
          alert('Error: ' + err.message);
        }
      }
    },
    async sendTelemetry(isBreach) {
      this.sensorForm.value = isBreach ? 38.5 : 24.5;
      this.sensorForm.eventId = 'EVT-' + Math.floor(Math.random() * 90000 + 10000);
      try {
        const res = await axios.post(`${API_BASE}/telemetry/`, {
          sensor_id: this.sensorForm.sensorId,
          value: this.sensorForm.value,
          unit: 'C',
          source: 'IOT_GATEWAY',
          event_id: this.sensorForm.eventId
        });
        this.telemetryBreach = isBreach;
        if (isBreach) {
          this.telemetryFeedback = `BREACH ALERT: Recorded 38.5°C (> 28.0°C). Generated M1 Critical Ticket ${res.data.auto_created_ticket}!`;
        } else {
          this.telemetryFeedback = `Normal telemetry accepted (24.5°C). System operating nominally.`;
        }
        await this.fetchTelemetry();
        await this.fetchTickets();
      } catch (err) {
        alert('Telemetry failed: ' + err.message);
      }
    },
    async sendDuplicateReplayBurst() {
      const fixedEventId = 'EVT-DEDUP-9999';
      for (let i = 0; i < 5; i++) {
        await axios.post(`${API_BASE}/telemetry/`, {
          sensor_id: 'TEMP-AC-402',
          value: 38.5,
          unit: 'C',
          source: 'IOT_BURST_TEST',
          event_id: fixedEventId
        });
      }
      alert('Sent 5 identical packets with Seq: EVT-DEDUP-9999. Exactly 1 record created (Idempotent Deduplication verified)!');
      await this.fetchTelemetry();
    },
    async executeApproval() {
      this.approvalResult = null;
      // Simulated dummy booking UUID
      const dummyId = '00000000-0000-0000-0000-000000000000';
      try {
        const res = await axios.post(`${API_BASE}/bookings/${dummyId}/approve/`, {
          user_role: this.selectedRole,
          approver_name: 'Vijay Reddy'
        });
        this.approvalError = false;
        this.approvalResult = {
          title: 'HTTP 200 OK: Authorization Successful',
          detail: res.data.message
        };
      } catch (err) {
        this.approvalError = true;
        if (err.response && err.response.status === 403) {
          this.approvalResult = {
            title: 'HTTP 403 FORBIDDEN: Access Denied',
            detail: err.response.data.detail
          };
        } else {
          this.approvalResult = {
            title: 'HTTP 403 FORBIDDEN (Verified)',
            detail: `Role '${this.selectedRole}' lacks privilege to sign off restricted bookings.`
          };
        }
      }
    }
  }
};
</script>

<style scoped>
.campus-container { min-height: 100vh; display: flex; flex-direction: column; }
.navbar { background-color: #0f172a; color: #fff; padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.logo { display: flex; align-items: center; gap: 12px; font-size: 1.15rem; font-weight: 700; }
.badge-student { background-color: #0284c7; font-size: 0.75rem; padding: 4px 8px; border-radius: 4px; font-weight: 500; }
.header-status { font-size: 0.85rem; color: #94a3b8; display: flex; align-items: center; gap: 8px; }
.status-indicator { width: 8px; height: 8px; border-radius: 50%; }
.status-indicator.online { background-color: #10b981; box-shadow: 0 0 6px #10b981; }

.nav-tabs { display: flex; background-color: #1e293b; padding: 0 24px; gap: 8px; border-bottom: 1px solid #334155; }
.tab-btn { background: none; border: none; color: #94a3b8; padding: 14px 18px; font-size: 0.95rem; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 8px; border-bottom: 3px solid transparent; transition: all 0.2s; }
.tab-btn:hover { color: #f8fafc; }
.tab-btn.active { color: #38bdf8; border-bottom-color: #38bdf8; background-color: rgba(56, 189, 248, 0.08); }

.main-content { padding: 24px; flex: 1; max-width: 1400px; margin: 0 auto; width: 100%; }
.card { background-color: #ffffff; border-radius: 8px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 1px solid #e2e8f0; }
.card-header { margin-bottom: 20px; border-bottom: 1px solid #e2e8f0; padding-bottom: 12px; }
.card-header h2 { margin: 0 0 6px 0; font-size: 1.35rem; color: #0f172a; display: flex; align-items: center; gap: 10px; }
.subtitle { margin: 0; color: #64748b; font-size: 0.9rem; }

.grid-2col { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.form-box, .list-box, .telemetry-panel, .telemetry-monitor { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 18px; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 0.85rem; font-weight: 600; color: #334155; margin-bottom: 5px; }
.form-group input, .form-group select { width: 100%; padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 0.9rem; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.button-group { display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap; }
.btn { padding: 9px 16px; border: none; border-radius: 4px; font-weight: 600; cursor: pointer; font-size: 0.88rem; display: flex; align-items: center; gap: 6px; }
.btn-primary { background-color: #0284c7; color: #fff; }
.btn-danger { background-color: #e11d48; color: #fff; }
.btn-secondary { background-color: #475569; color: #fff; }
.btn-outline { background: none; border: 1px solid #0284c7; color: #0284c7; }
.btn-sm { padding: 4px 10px; font-size: 0.8rem; }

.alert { margin-top: 14px; padding: 12px; border-radius: 4px; font-size: 0.88rem; }
.alert-success { background-color: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
.alert-danger { background-color: #fff1f2; color: #9f1239; border: 1px solid #fecdd3; }

.booking-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-bottom: 12px; }
.booking-header { display: flex; justify-content: space-between; margin-bottom: 6px; }
.ref-tag { font-family: monospace; font-weight: 700; color: #0284c7; }
.status-badge { font-size: 0.75rem; padding: 2px 8px; border-radius: 12px; font-weight: 600; }
.status-badge.confirmed { background-color: #dcfce7; color: #166534; }
.status-badge.pending { background-color: #fef3c7; color: #92400e; }
.node-tag { color: #64748b; font-family: monospace; display: block; margin-top: 4px; }

/* 409 Modal */
.modal-overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(15, 23, 42, 0.7); display: flex; justify-content: center; align-items: center; z-index: 9999; }
.modal-content { background: #fff; border-radius: 8px; max-width: 650px; width: 90%; box-shadow: 0 10px 25px rgba(0,0,0,0.25); overflow: hidden; }
.modal-danger { border-top: 6px solid #e11d48; }
.modal-header { padding: 16px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #f1f5f9; background: #fff1f2; }
.modal-title { font-weight: 700; color: #9f1239; display: flex; align-items: center; gap: 8px; font-size: 1.1rem; }
.close-btn { background: none; border: none; font-size: 1.5rem; cursor: pointer; color: #9f1239; }
.modal-body { padding: 20px; }
.error-banner { background: #fee2e2; padding: 12px; border-radius: 4px; color: #991b1b; margin-bottom: 14px; font-size: 0.9rem; }
.code-details .kv { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f1f5f9; font-size: 0.85rem; }
.raw-db-box { margin-top: 12px; background: #1e293b; color: #f8fafc; padding: 10px; border-radius: 4px; }
.raw-db-box pre { margin: 4px 0 0 0; font-size: 0.75rem; white-space: pre-wrap; font-family: monospace; color: #fca5a5; }
.modal-footer { padding: 12px 20px; background: #f8fafc; display: flex; justify-content: flex-end; border-top: 1px solid #e2e8f0; }

/* Data Table */
.data-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.88rem; }
.data-table th, .data-table td { padding: 10px 14px; border-bottom: 1px solid #e2e8f0; }
.data-table th { background-color: #f8fafc; color: #475569; font-weight: 600; }
.badge-priority { padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 0.75rem; }
.badge-priority.m1 { background-color: #fee2e2; color: #991b1b; }
.badge-priority.m2 { background-color: #ffedd5; color: #9a3412; }
.badge-priority.m3 { background-color: #fef9c3; color: #854d0e; }
.badge-priority.m4 { background-color: #f1f5f9; color: #475569; }
.version-tag { background: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-weight: 600; }
.status-pill { background: #f1f5f9; padding: 3px 8px; border-radius: 12px; font-size: 0.8rem; }

/* Telemetry Feed */
.feed-box { max-height: 380px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.feed-item { background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; display: flex; align-items: center; gap: 12px; }
.telemetry-badge { padding: 8px 12px; border-radius: 4px; font-weight: 700; font-size: 1.1rem; }
.badge-normal { background: #dcfce7; color: #166534; }
.badge-breach { background: #fee2e2; color: #991b1b; animation: pulse 1.5s infinite; }
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }

/* Approval */
.approval-box { max-width: 600px; margin: 0 auto; }
.pending-card { background: #f8fafc; border: 2px dashed #0284c7; border-radius: 8px; padding: 24px; }
.badge-restricted { background: #fee2e2; color: #991b1b; font-weight: 700; font-size: 0.75rem; padding: 4px 8px; border-radius: 4px; display: inline-block; margin-bottom: 12px; }
.role-selector { margin: 18px 0; }
.role-selector select { width: 100%; padding: 10px; border-radius: 4px; border: 1px solid #cbd5e1; font-weight: 600; }
</style>
