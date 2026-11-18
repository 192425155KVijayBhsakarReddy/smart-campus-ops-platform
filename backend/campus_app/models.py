from django.db import models
from django.db.models import Q
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.contrib.postgres.constraints import ExclusionConstraint
import uuid

class Room(models.Model):
    room_code = models.CharField(max_length=32, unique=True, primary_key=True)
    name = models.CharField(max_length=128)
    capacity = models.PositiveIntegerField(default=30)
    is_restricted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.room_code} - {self.name}"

class Booking(models.Model):
    STATUS_CHOICES = [
        ('CONFIRMED', 'Confirmed'),
        ('PENDING_APPROVAL', 'Pending Approval'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_reference = models.CharField(max_length=32, unique=True)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings')
    booked_by = models.CharField(max_length=64)
    user_role = models.CharField(max_length=32, default='FACULTY')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    time_slot = DateTimeRangeField(help_text="PostgreSQL tstzrange for GiST exclusion constraint")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='CONFIRMED')
    purpose = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # PostgreSQL btree_gist Exclusion Constraint:
        # Prevents overlapping bookings for the same room when status is active!
        constraints = [
            ExclusionConstraint(
                name='exclude_overlapping_bookings',
                expressions=[
                    ('room', RangeOperators.EQUAL),
                    ('time_slot', RangeOperators.OVERLAPS),
                ],
                condition=Q(status__in=['CONFIRMED', 'PENDING_APPROVAL']),
            )
        ]

    def __str__(self):
        return f"{self.booking_reference} | {self.room_id} [{self.start_time} - {self.end_time}] ({self.status})"

class MaintenanceTicket(models.Model):
    PRIORITY_CHOICES = [
        ('M1', 'M1 - Critical / Emergency (SLA: 2h)'),
        ('M2', 'M2 - High Operational Impact (SLA: 6h)'),
        ('M3', 'M3 - Medium Scheduled Work (SLA: 24h)'),
        ('M4', 'M4 - Low Routine Maintenance (SLA: 72h)'),
    ]
    STATUS_CHOICES = [
        ('REPORTED', 'Reported'),
        ('TRIAGED', 'Triaged'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ]

    ticket_number = models.CharField(max_length=32, unique=True)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=64, default='FACILITIES')
    impact = models.CharField(max_length=16, default='MEDIUM')
    urgency = models.CharField(max_length=16, default='MEDIUM')
    priority = models.CharField(max_length=4, choices=PRIORITY_CHOICES, default='M3')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='REPORTED')
    # Optimistic Concurrency Control Version Counter:
    version = models.PositiveIntegerField(default=1, help_text="Optimistic version locking counter")
    assigned_to = models.CharField(max_length=64, blank=True, null=True)
    resolution_notes = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=64, default='MANUAL')
    event_id = models.CharField(max_length=128, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ticket_number} | {self.priority} | {self.title} [v{self.version}]"

class SensorTelemetry(models.Model):
    sensor_id = models.CharField(max_length=64)
    metric_type = models.CharField(max_length=32, default='TEMPERATURE')
    value = models.FloatField()
    unit = models.CharField(max_length=16, default='C')
    source = models.CharField(max_length=64, default='IOT_SENSOR_GATEWAY')
    event_id = models.CharField(max_length=128)
    is_breach = models.BooleanField(default=False)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('source', 'event_id')

    def __str__(self):
        return f"{self.sensor_id}: {self.value}{self.unit} ({'BREACH' if self.is_breach else 'NORMAL'})"

class AuditEvent(models.Model):
    entity_type = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64)
    action = models.CharField(max_length=64)
    from_state = models.CharField(max_length=64, blank=True, null=True)
    to_state = models.CharField(max_length=64, blank=True, null=True)
    actor = models.CharField(max_length=64)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.timestamp}] {self.entity_type} {self.entity_id}: {self.action} ({self.from_state}->{self.to_state}) by {self.actor}"
