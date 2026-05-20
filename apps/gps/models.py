from django.db import models
from django.conf import settings

class GPSPoint(models.Model):
    driver      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='gps_points')
    vehicle_id  = models.PositiveIntegerField()
    vehicle_type= models.CharField(max_length=10, default='bus')
    latitude    = models.DecimalField(max_digits=10, decimal_places=7)
    longitude   = models.DecimalField(max_digits=10, decimal_places=7)
    speed_kmh   = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"{self.driver} [{self.latitude},{self.longitude}] @ {self.recorded_at:%H:%M:%S}"
