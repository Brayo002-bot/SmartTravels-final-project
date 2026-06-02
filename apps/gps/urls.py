from django.urls import path
from . import views

urlpatterns = [
    path('',                               views.live_tracking,      name='live_tracking'),
    path('update/',                        views.update_gps,         name='gps_update'),
    path('track/<str:booking_reference>/', views.passenger_track_journey, name='track_by_booking'),
    path('track/<str:vehicle_type>/<int:vehicle_id>/', views.passenger_track_journey, name='vehicle_location'),
    path('<str:vehicle_type>/<int:vehicle_id>/', views.get_vehicle_location, name='get_vehicle_location'),
]
