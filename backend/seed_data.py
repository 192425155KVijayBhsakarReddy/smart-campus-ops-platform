import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'campus_project.settings')
django.setup()

from campus_app.models import Room, MaintenanceTicket, SensorTelemetry

def seed():
    rooms = [
        {"room_code": "LAB-201", "name": "Advanced Robotics & AI Lab", "capacity": 35, "is_restricted": True},
        {"room_code": "LAB-204", "name": "Microprocessor & Embedded Systems Lab", "capacity": 40, "is_restricted": True},
        {"room_code": "AUD-101", "name": "Main Academic Auditorium", "capacity": 250, "is_restricted": False},
        {"room_code": "CONF-301", "name": "Faculty Boardroom", "capacity": 20, "is_restricted": True},
        {"room_code": "LEC-105", "name": "Smart Lecture Theatre 105", "capacity": 60, "is_restricted": False},
    ]
    for r in rooms:
        Room.objects.get_or_create(room_code=r["room_code"], defaults=r)
    print("Rooms seeded successfully.")

    if not MaintenanceTicket.objects.exists():
        MaintenanceTicket.objects.create(
            ticket_number="TKT-1042",
            title="HVAC cooling efficiency degraded in Server Room 2",
            category="HVAC",
            impact="HIGH",
            urgency="HIGH",
            priority="M1",
            status="IN_PROGRESS",
            version=7,
            assigned_to="Tech Sarah",
            source="IOT:TEMP-AC-402"
        )
        MaintenanceTicket.objects.create(
            ticket_number="TKT-1038",
            title="Projector HDMI handshake flicker in AUD-101",
            category="AV-NETWORK",
            impact="MEDIUM",
            urgency="MEDIUM",
            priority="M3",
            status="TRIAGED",
            version=2,
            assigned_to="Tech Bob",
            source="MANUAL"
        )
        print("Sample maintenance tickets seeded.")

if __name__ == '__main__':
    seed()
