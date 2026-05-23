# apps/trains/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.train_dashboard, name='train_dashboard'),
    path('add-route/', views.add_route, name='train_add_route'),
    path('edit-route/<int:route_id>/', views.edit_route, name='train_edit_route'),
    path('delete-route/<int:route_id>/', views.delete_route, name='train_delete_route'),
    path('reports/', views.reports, name='train_reports'),
    path('booking/', views.booking, name='train_booking'),
    path('api/available-seats/', views.get_available_seats, name='train_get_available_seats'),
    path('schedule/', views.schedule, name='train_schedule'),
    path('add-conductor/', views.add_conductor, name='add_conductor'),
    path('add-trains/', views.add_trains, name='add_trains'),
    path('cargo/', views.cargo, name='train_cargo'),
    path('traffic/', views.traffic, name='train_traffic'),
    path('edit-train/<int:train_id>/', views.edit_train, name='train_edit_train'),
    path('delete-train/<int:train_id>/', views.delete_train, name='train_delete_train'),
    path('seat-preview/', views.train_seat_preview, name='train_seat_preview'),
    path('generate-layout/', views.generate_train_layout, name='generate_train_layout'),
    path('company-profile/', views.company_profile, name='train_company_profile'),
]