from rest_framework import serializers
from .models import Room, Booking, MaintenanceTicket, SensorTelemetry, AuditEvent
from psycopg2.extras import DateTimeTZRange
from django.utils.dateparse import parse_datetime

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = '__all__'

class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = [
            'id', 'booking_reference', 'room', 'booked_by', 'user_role',
            'start_time', 'end_time', 'status', 'purpose', 'created_at'
        ]
        read_only_fields = ['id', 'booking_reference', 'created_at']

    def create(self, validated_data):
        import uuid
        start = validated_data['start_time']
        end = validated_data['end_time']
        if end <= start:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})
        
        # Calculate tstzrange for PostgreSQL GiST exclusion constraint
        validated_data['time_slot'] = DateTimeTZRange(start, end, bounds='[)')
        if 'booking_reference' not in validated_data or not validated_data['booking_reference']:
            validated_data['booking_reference'] = f"BK-{uuid.uuid4().hex[:8].upper()}"
        return super().create(validated_data)

class MaintenanceTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceTicket
        fields = '__all__'
        read_only_fields = ['id', 'ticket_number', 'created_at', 'updated_at']

class SensorTelemetrySerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorTelemetry
        fields = '__all__'

class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = '__all__'
