from django.urls import path
from . import views

urlpatterns = [
    path('',       views.notification_list, name='notifications'),
    path('count/', views.unread_count,      name='notif_count'),
]
