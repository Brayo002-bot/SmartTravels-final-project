from django.db import models
from django.conf import settings

class Notification(models.Model):
    TYPE = [('booking','Booking'),('payment','Payment'),('parcel','Parcel'),
            ('alert','Alert'),('system','System')]
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title      = models.CharField(max_length=200)
    message    = models.TextField()
    ntype      = models.CharField(max_length=20, choices=TYPE, default='system')
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user}: {self.title}"

def notify(user, title, message, ntype='system'):
    Notification.objects.create(user=user, title=title, message=message, ntype=ntype)
