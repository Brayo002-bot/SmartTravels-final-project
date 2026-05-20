from django.urls import path
from . import views

urlpatterns = [
    path('',       views.parcel_view,  name='parcel'),
    path('scan/',  views.scan_parcel,  name='scan_parcel'),
]
