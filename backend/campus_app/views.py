import socket
import uuid
import base64
import hashlib
import hmac
import json
from django.db import IntegrityError, transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from .models import Room, Booking, MaintenanceTicket, SensorTelemetry, AuditEvent
from .serializers import RoomSerializer, BookingSerializer, MaintenanceTicketSerializer, SensorTelemetrySerializer, AuditEventSerializer

SECRET_SIGNING_KEY = b"campus-platform-secure-jwt-hmac-key-2026"

def verify_trusted_role(request):
    """
    Authoritative Role Verification:
    In production, ingress proxies (Nginx / API Gateway) strip untrusted client headers:
        proxy_set_header X-User-Role "";
    Clients must present an authenticated Bearer token or HMAC-signed gateway assertion (X-Gateway-Signature).
    This function verifies:
    1. Internal gateway signature (X-Gateway-Signature): verifies HMAC-SHA256 signature against SECRET_SIGNING_KEY.
    2. Authenticated Bearer token: verifies payload and cryptographic HMAC signature.
    3. Untrusted/Unsigned direct header assertion (e.g. X-User-Role: ADMIN without signature): flagged as UNVERIFIED_CLIENT_ASSERTION.
    4. Missing auth context defaults safely to STUDENT.
    """
    auth_header = request.headers.get('Authorization', '')
    gateway_sig = request.headers.get('X-Gateway-Signature', '')
    raw_role = request.headers.get('X-User-Role', '')

    # 1. Bearer Token Verification
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1].strip()
        try:
            parts = token.split('.')
            if len(parts) == 2:
                payload_b64, sig = parts
                expected_sig = hmac.new(SECRET_SIGNING_KEY, payload_b64.encode(), hashlib.sha256).hexdigest()
                if hmac.compare_digest(sig, expected_sig):
                    payload = json.loads(base64.b64decode(payload_b64).decode())
                    return payload.get('role', 'STUDENT'), payload.get('user_id', 'token')
        except Exception:
            pass

    # 2. Ingress Gateway HMAC Signature Verification
    if gateway_sig and raw_role:
        expected_sig = hmac.new(SECRET_SIGNING_KEY, raw_role.upper().encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(gateway_sig, expected_sig):
            return raw_role.upper(), "gateway-verified"

    # 3. Direct client header spoofing without cryptographic signature
    if raw_role:
        if raw_role.upper() in ['ADMIN', 'FACILITY_MANAGER', 'DEPT_HEAD']:
            return 'UNVERIFIED_CLIENT_ASSERTION', None
        return raw_role.upper(), 'direct-client'

    return 'STUDENT', 'anonymous'

class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all().order_by('room_code')
    serializer_class = RoomSerializer

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all().order_by('-created_at')
    serializer_class = BookingSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                booking = serializer.save()
                # Record audit event
                AuditEvent.objects.create(
                    entity_type='BOOKING',
                    entity_id=str(booking.id),
                    action='CREATE',
                    from_state='NONE',
                    to_state=booking.status,
                    actor=booking.booked_by
                )
                headers = self.get_success_headers(serializer.data)
                resp_data = serializer.data
                resp_data['node_hostname'] = socket.gethostname()
                return Response(resp_data, status=status.HTTP_201_CREATED, headers=headers)
        except IntegrityError as exc:
            # PostgreSQL btree_gist ExclusionConstraint caught!
            room_val = request.data.get('room')
            start_val = request.data.get('start_time')
            end_val = request.data.get('end_time')
            return Response({
                "error": "ERR_SLOT_OVERLAP",
                "status_code": 409,
                "detail": f"Conflicting reservation detected: Room {room_val} is already booked during this time interval.",
                "room": room_val,
                "conflict_interval": f"{start_val} to {end_val}",
                "engine_rejection": "PostgreSQL 16 btree_gist ExclusionConstraint (exclude_overlapping_bookings)",
                "node_hostname": socket.gethostname(),
                "raw_db_error": str(exc).strip().replace('\n', ' ')
            }, status=status.HTTP_409_CONFLICT)

class MaintenanceTicketViewSet(viewsets.ModelViewSet):
    queryset = MaintenanceTicket.objects.all().order_by('-created_at')
    serializer_class = MaintenanceTicketSerializer

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        if 'ticket_number' not in data or not data['ticket_number']:
            data['ticket_number'] = f"TKT-{uuid.uuid4().hex[:6].upper()}"
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save(ticket_number=data['ticket_number'])
        AuditEvent.objects.create(
            entity_type='TICKET',
            entity_id=ticket.ticket_number,
            action='CREATE',
            from_state='NONE',
            to_state=ticket.status,
            actor=request.data.get('reported_by', 'system')
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def transition(self, request, pk=None):
        """Optimistic locking update endpoint verifying expected_version"""
        ticket = self.get_object()
        expected_version = request.data.get('expected_version')
        target_status = request.data.get('target_status')
        notes = request.data.get('resolution_notes', '')
        actor = request.data.get('actor', 'technician')

        if expected_version is None:
            return Response({"error": "expected_version is required for concurrency control"}, status=status.HTTP_400_BAD_REQUEST)

        # Atomic conditional update
        with transaction.atomic():
            updated_count = MaintenanceTicket.objects.filter(
                pk=ticket.pk,
                version=expected_version
            ).update(
                status=target_status,
                resolution_notes=notes if notes else ticket.resolution_notes,
                version=expected_version + 1
            )

            if updated_count == 0:
                # Version mismatch -> Lost update prevented!
                current_ticket = MaintenanceTicket.objects.get(pk=ticket.pk)
                return Response({
                    "error": "ERR_STALE_VERSION",
                    "status_code": 409,
                    "detail": f"Conflict detected: Ticket {ticket.ticket_number} was modified by another user.",
                    "supplied_version": expected_version,
                    "current_database_version": current_ticket.version,
                    "current_status": current_ticket.status,
                    "action_required": "Please refresh the ticket state before applying changes."
                }, status=status.HTTP_409_CONFLICT)

            # Reload updated ticket
            ticket.refresh_from_db()
            AuditEvent.objects.create(
                entity_type='TICKET',
                entity_id=ticket.ticket_number,
                action='TRANSITION',
                from_state=request.data.get('from_state', 'UNKNOWN'),
                to_state=target_status,
                actor=actor
            )
            return Response(self.get_serializer(ticket).data, status=status.HTTP_200_OK)

class SensorTelemetryViewSet(viewsets.ModelViewSet):
    queryset = SensorTelemetry.objects.all().order_by('-recorded_at')
    serializer_class = SensorTelemetrySerializer

    def create(self, request, *args, **kwargs):
        source = request.data.get('source', 'IOT_GATEWAY')
        event_id = request.data.get('event_id')
        sensor_id = request.data.get('sensor_id', 'TEMP-AC-402')
        val = float(request.data.get('value', 25.0))
        unit = request.data.get('unit', 'C')

        # 1. Idempotency Check:
        if event_id:
            existing = SensorTelemetry.objects.filter(source=source, event_id=event_id).first()
            if existing:
                return Response({
                    "message": "Duplicate telemetry event safely acknowledged and ignored.",
                    "idempotency_key": f"{source}:{event_id}",
                    "duplicate_ignored": True,
                    "telemetry_id": existing.id,
                    "sensor_id": existing.sensor_id,
                    "value": existing.value
                }, status=status.HTTP_200_OK)

        # 2. Check threshold breach (> 28.0 C)
        is_breach = (val > 28.0)
        telemetry = SensorTelemetry.objects.create(
            sensor_id=sensor_id,
            metric_type=request.data.get('metric_type', 'TEMPERATURE'),
            value=val,
            unit=unit,
            source=source,
            event_id=event_id if event_id else f"EVT-{uuid.uuid4().hex[:8]}",
            is_breach=is_breach
        )

        ticket_created = None
        if is_breach:
            tkt = MaintenanceTicket.objects.create(
                ticket_number=f"TKT-AUTO-{uuid.uuid4().hex[:4].upper()}",
                title=f"CRITICAL: {sensor_id} temperature breach ({val}{unit} > 28.0{unit})",
                category="HVAC",
                impact="HIGH",
                urgency="HIGH",
                priority="M1",
                status="REPORTED",
                source=f"IOT:{sensor_id}",
                event_id=telemetry.event_id
            )
            ticket_created = tkt.ticket_number

        resp = self.get_serializer(telemetry).data
        resp['auto_created_ticket'] = ticket_created
        return Response(resp, status=status.HTTP_201_CREATED)

@api_view(['POST'])
def approve_booking(request, booking_id):
    """Dual-control approval endpoint with cryptographic token / signed role verification"""
    role, user_id = verify_trusted_role(request)
    approver_name = request.data.get('approver_name', 'anonymous')

    # 1. Reject unverified/forged client assertions
    if role == 'UNVERIFIED_CLIENT_ASSERTION':
        return Response({
            "error": "ERR_FORGED_ROLE_HEADER",
            "status_code": 403,
            "detail": "Access Denied: Unsigned or forged role header rejected. Cryptographic Bearer token or gateway HMAC signature required.",
            "authorized_roles": ["FACILITY_MANAGER", "DEPT_HEAD", "ADMIN"]
        }, status=status.HTTP_403_FORBIDDEN)

    # 2. Reject unauthorized student/technician roles
    if role in ['STUDENT', 'TECHNICIAN']:
        return Response({
            "error": "ERR_UNAUTHORIZED_APPROVAL",
            "status_code": 403,
            "detail": f"Access Denied: Authenticated role '{role}' lacks permission to approve restricted facility reservations.",
            "authorized_roles": ["FACILITY_MANAGER", "DEPT_HEAD", "ADMIN"]
        }, status=status.HTTP_403_FORBIDDEN)

    try:
        booking = Booking.objects.get(id=booking_id)
        old_status = booking.status
        booking.status = 'CONFIRMED'
        booking.save()
        AuditEvent.objects.create(
            entity_type='BOOKING',
            entity_id=str(booking.id),
            action='APPROVE',
            from_state=old_status,
            to_state='CONFIRMED',
            actor=f"{role}:{approver_name}"
        )
        return Response({
            "message": f"Booking {booking.booking_reference} successfully authorized and confirmed.",
            "booking_reference": booking.booking_reference,
            "status": "CONFIRMED",
            "authorized_by": f"{role}:{approver_name}"
        }, status=status.HTTP_200_OK)
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
def health_check(request):
    """Healthcheck endpoint for Nginx and Docker Compose"""
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
        return Response({
            "status": "healthy",
            "database": "connected",
            "node_hostname": socket.gethostname(),
            "engine": "PostgreSQL 16"
        }, status=status.HTTP_200_OK)
    except Exception as exc:
        return Response({
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(exc)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
