from django.contrib import admin
from .models import GPSPoint
@admin.register(GPSPoint)
class GPSPointAdmin(admin.ModelAdmin):
    list_display = ('driver','vehicle_type','vehicle_id','latitude','longitude','speed_kmh','recorded_at')
    list_filter = ('vehicle_type',)
