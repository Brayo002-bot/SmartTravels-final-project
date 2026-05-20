from django.urls import path
from . import views

urlpatterns = [
    path('',                               views.live_tracking,      name='live_tracking'),
    path('update/',                        views.update_gps,         name='gps_update'),
    path('<str:vehicle_type>/<int:vehicle_id>/', views.get_vehicle_location, name='vehicle_location'),
]
