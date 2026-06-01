from django.urls import path
from . import views
from . import seat_views

urlpatterns = [
    path('dashboard/',          views.system_admin_dashboard, name='system_admin_dashboard'),
    path('seat-layout-builder/', views.seat_layout_builder,     name='seat_layout_builder'),
    path('users/',              views.manage_users,           name='manage_users'),
    path('users/<int:user_id>/toggle/', views.toggle_user_status, name='toggle_user_status'),
    path('admins/',             views.manage_admins,          name='manage_admins'),
     path('companies/',          views.manage_companies,       name='manage_companies'),
    path('analytics/',          views.analytics,              name='system_analytics'),
    path('reports/',             views.analytics,              name='system_reports'),
    path('audit/',              views.audit_logs,             name='audit_logs'),
    path('settings/',           views.system_settings,        name='system_settings'),
    path('subscribers/',        views.subscribers,            name='subscribers'),
    path('subscribe/',          views.subscribe,              name='subscribe'),
    
    # Seat Management API
    path('api/seats/vehicle/<str:vehicle_type>/<int:vehicle_id>/<str:travel_date>/', 
         seat_views.get_vehicle_seats, name='get_vehicle_seats'),
    path('api/seats/<int:seat_id>/', 
         seat_views.get_seat_details, name='get_seat_details'),
    path('api/seats/<int:seat_id>/reserve/', 
         seat_views.reserve_seat, name='reserve_seat'),
    path('api/seats/<int:seat_id>/release/', 
         seat_views.release_seat, name='release_seat'),
    path('api/seats/confirm-booking/', 
         seat_views.confirm_seat_booking, name='confirm_seat_booking'),
    path('api/seats/layout/<int:layout_id>/', 
         seat_views.get_seat_layout_template, name='get_seat_layout_template'),
    path('api/seats/templates/<str:vehicle_type>/', 
         seat_views.list_available_templates, name='list_available_templates'),
    path('api/seats/my-reservations/', 
         seat_views.get_user_reservations, name='get_user_reservations'),
    path('api/seats/generate/', 
         seat_views.generate_vehicle_seats, name='generate_vehicle_seats'),
]
