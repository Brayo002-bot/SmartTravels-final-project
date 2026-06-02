from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('route-suggestions/', views.passenger_route_suggestions, name='passenger_route_suggestions'),
    path('bookings/', views.passenger_my_bookings, name='my_bookings'),
    path('tickets/', views.passenger_tickets, name='tickets'),
    path('payments/', views.passenger_payments, name='payments'),
    path('track-parcel/', views.passenger_track_parcel, name='track_parcel'),
    path('loyalty/', views.passenger_loyalty, name='loyalty'),
    path('support/', views.passenger_support, name='support'),
    path('traffic/', views.passenger_traffic_alerts, name='traffic_alerts'),
    path('book-trip/<str:mode>/<int:schedule_id>/', views.book_trip, name='book_trip'),
    path('seat-layout/', views.passenger_seat_layout, name='passenger_seat_layout'),
    path('ticket-preview/<str:booking_reference>/', views.booking_ticket_preview, name='booking_ticket_preview'),
    path('download-ticket/<str:booking_reference>/', views.download_ticket, name='download_ticket'),
]