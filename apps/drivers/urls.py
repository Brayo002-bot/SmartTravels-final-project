from django.urls import path
from . import views

urlpatterns = [
    path('', views.driver_dashboard, name='driver_dashboard'),
    path('start-journey/', views.start_journey, name='start_journey'),
    path('end-journey/', views.end_journey, name='end_journey'),
    path('update-location/', views.update_location, name='update_location'),
    path('manifest-api/', views.manifest_api, name='manifest_api'),
    path('stop-passenger-tracking/<int:pk>/', views.stop_passenger_tracking, name='stop_passenger_tracking'),
    path('link-profile/', views.link_driver_profile, name='link_driver_profile'),
]
