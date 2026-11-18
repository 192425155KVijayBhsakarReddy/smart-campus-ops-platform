from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoomViewSet, BookingViewSet, MaintenanceTicketViewSet, SensorTelemetryViewSet, approve_booking, health_check

router = DefaultRouter()
router.register(r'rooms', RoomViewSet, basename='room')
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'tickets', MaintenanceTicketViewSet, basename='ticket')
router.register(r'telemetry', SensorTelemetryViewSet, basename='telemetry')

urlpatterns = [
    path('', include(router.urls)),
    path('bookings/<uuid:booking_id>/approve/', approve_booking, name='approve_booking'),
    path('healthz/', health_check, name='health_check'),
]
