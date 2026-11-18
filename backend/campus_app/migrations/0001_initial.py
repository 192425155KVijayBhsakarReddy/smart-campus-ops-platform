from django.db import migrations, models
import django.db.models.deletion
from django.contrib.postgres.operations import BtreeGistExtension
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.contrib.postgres.constraints import ExclusionConstraint
from django.db.models import Q
import uuid

class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # 1. Enable btree_gist extension in PostgreSQL 16
        BtreeGistExtension(),

        # 2. Room Table
        migrations.CreateModel(
            name='Room',
            fields=[
                ('room_code', models.CharField(max_length=32, primary_key=True, serialize=False, unique=True)),
                ('name', models.CharField(max_length=128)),
                ('capacity', models.PositiveIntegerField(default=30)),
                ('is_restricted', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),

        # 3. Booking Table with PostgreSQL ExclusionConstraint
        migrations.CreateModel(
            name='Booking',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('booking_reference', models.CharField(max_length=32, unique=True)),
                ('booked_by', models.CharField(max_length=64)),
                ('user_role', models.CharField(default='FACULTY', max_length=32)),
                ('start_time', models.DateTimeField()),
                ('end_time', models.DateTimeField()),
                ('time_slot', DateTimeRangeField(help_text='PostgreSQL tstzrange for GiST exclusion constraint')),
                ('status', models.CharField(choices=[('CONFIRMED', 'Confirmed'), ('PENDING_APPROVAL', 'Pending Approval'), ('CANCELLED', 'Cancelled'), ('COMPLETED', 'Completed')], default='CONFIRMED', max_length=32)),
                ('purpose', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookings', to='campus_app.room')),
            ],
        ),
        migrations.AddConstraint(
            model_name='booking',
            constraint=ExclusionConstraint(
                condition=Q(('status__in', ['CONFIRMED', 'PENDING_APPROVAL'])),
                expressions=[('room', RangeOperators.EQUAL), ('time_slot', RangeOperators.OVERLAPS)],
                name='exclude_overlapping_bookings'
            ),
        ),

        # 4. Maintenance Ticket Table with Optimistic Versioning
        migrations.CreateModel(
            name='MaintenanceTicket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ticket_number', models.CharField(max_length=32, unique=True)),
                ('title', models.CharField(max_length=255)),
                ('category', models.CharField(default='FACILITIES', max_length=64)),
                ('impact', models.CharField(default='MEDIUM', max_length=16)),
                ('urgency', models.CharField(default='MEDIUM', max_length=16)),
                ('priority', models.CharField(choices=[('M1', 'M1 - Critical / Emergency (SLA: 2h)'), ('M2', 'M2 - High Operational Impact (SLA: 6h)'), ('M3', 'M3 - Medium Scheduled Work (SLA: 24h)'), ('M4', 'M4 - Low Routine Maintenance (SLA: 72h)')], default='M3', max_length=4)),
                ('status', models.CharField(choices=[('REPORTED', 'Reported'), ('TRIAGED', 'Triaged'), ('IN_PROGRESS', 'In Progress'), ('RESOLVED', 'Resolved'), ('CLOSED', 'Closed')], default='REPORTED', max_length=32)),
                ('version', models.PositiveIntegerField(default=1, help_text='Optimistic version locking counter')),
                ('assigned_to', models.CharField(blank=True, max_length=64, null=True)),
                ('resolution_notes', models.TextField(blank=True, null=True)),
                ('source', models.CharField(default='MANUAL', max_length=64)),
                ('event_id', models.CharField(blank=True, max_length=128, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),

        # 5. Sensor Telemetry Table with Idempotency
        migrations.CreateModel(
            name='SensorTelemetry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sensor_id', models.CharField(max_length=64)),
                ('metric_type', models.CharField(default='TEMPERATURE', max_length=32)),
                ('value', models.FloatField()),
                ('unit', models.CharField(default='C', max_length=16)),
                ('source', models.CharField(default='IOT_SENSOR_GATEWAY', max_length=64)),
                ('event_id', models.CharField(max_length=128)),
                ('is_breach', models.BooleanField(default=False)),
                ('recorded_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'unique_together': {('source', 'event_id')},
            },
        ),

        # 6. Audit Event Table
        migrations.CreateModel(
            name='AuditEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entity_type', models.CharField(max_length=64)),
                ('entity_id', models.CharField(max_length=64)),
                ('action', models.CharField(max_length=64)),
                ('from_state', models.CharField(blank=True, max_length=64, null=True)),
                ('to_state', models.CharField(blank=True, max_length=64, null=True)),
                ('actor', models.CharField(max_length=64)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
