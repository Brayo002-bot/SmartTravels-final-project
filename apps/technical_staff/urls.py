from django.urls import path

from . import views

urlpatterns = [
    path('', views.tech_dashboard, name='tech_dashboard'),
    path('booking-assist/', views.tech_booking_assist, name='tech_booking_assist'),
    path('parcels/', views.tech_parcels, name='tech_parcels'),
    path('ticket-scanner/', views.tech_ticket_scanner, name='tech_ticket_scanner'),
    path('boarding/', views.tech_boarding, name='tech_boarding'),
    path('tracking/', views.tech_tracking, name='tech_tracking'),
    path('manage/', views.manage_technical_staff, name='manage_technical_staff'),
]
