# apps/flights/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.flight_dashboard, name='flight_dashboard'),
    path('add-route/', views.add_route, name='flight_add_route'),
    path('edit-route/<int:route_id>/', views.edit_route, name='flight_edit_route'),
    path('delete-route/<int:route_id>/', views.delete_route, name='flight_delete_route'),
    path('reports/', views.reports, name='flight_reports'),
    path('booking/', views.booking, name='flight_booking'),
    path('schedule/', views.schedule, name='flight_schedule'),
    path('add-pilot/', views.add_pilot, name='add_pilot'),
    path('add-flights/', views.add_flights, name='add_flights'),
    path('cargo/', views.cargo, name='flight_cargo'),
    path('traffic/', views.traffic, name='flight_traffic'),
    path('seat-preview/', views.flight_seat_preview, name='flight_seat_preview'),
    path('generate-layout/', views.generate_flight_layout, name='generate_flight_layout'),
    path('company-profile/', views.company_profile, name='flight_company_profile'),
]