# apps/buses/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.bus_dashboard, name='bus_dashboard'),
    path('add-route/', views.add_route, name='bus_add_route'),
    path('edit-route/<int:route_id>/', views.edit_route, name='bus_edit_route'),
    path('delete-route/<int:route_id>/', views.delete_route, name='bus_delete_route'),
    path('reports/', views.reports, name='bus_reports'),
    path('booking/', views.booking, name='bus_booking'),
    path('schedule/', views.schedule, name='bus_schedule'),
    path('add-driver/', views.add_driver, name='add_driver'),
    path('add-buses/', views.add_buses, name='add_buses'),
    path('cargo/', views.cargo, name='bus_cargo'),
    path('traffic/', views.traffic, name='bus_traffic'),
    path('edit-bus/<int:bus_id>/', views.edit_bus, name='bus_edit_bus'),
    path('delete-bus/<int:bus_id>/', views.delete_bus, name='bus_delete_bus'),
    path('seat-preview/', views.bus_seat_preview, name='bus_seat_preview'),
    path('generate-layout/', views.generate_bus_layout, name='generate_bus_layout'),
    path('company-profile/', views.company_profile, name='bus_company_profile'),
]