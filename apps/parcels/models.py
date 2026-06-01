import uuid
from django.db import models
from django.conf import settings

def parcel_id():
    return f"PKG-{uuid.uuid4().hex[:8].upper()}"

class Parcel(models.Model):
    STATUS = [
        ('booked','Booked'),('dropped_off','Dropped Off'),
        ('in_transit','In Transit'),('arrived','Arrived'),
        ('collected','Collected'),('returned','Returned'),
    ]
    CATEGORY = [
        ('documents','Documents'),('electronics','Electronics'),
        ('clothing','Clothing'),('food','Food/Perishables'),
        ('fragile','Fragile'),('other','Other'),
    ]
    parcel_id       = models.CharField(max_length=20, unique=True, default=parcel_id)
    sender          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_parcels')
    sender_name     = models.CharField(max_length=150)
    sender_phone    = models.CharField(max_length=20)
    sender_email    = models.EmailField(blank=True, default='')
    recipient_name  = models.CharField(max_length=150)
    recipient_phone = models.CharField(max_length=20)
    recipient_email = models.EmailField(blank=True, default='')
    origin          = models.CharField(max_length=100)
    destination     = models.CharField(max_length=100)
    category        = models.CharField(max_length=20, choices=CATEGORY, default='other')
    description     = models.TextField(blank=True)
    item_image      = models.ImageField(upload_to='parcel_images/', blank=True, null=True)
    weight_kg       = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    declared_value  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_fragile      = models.BooleanField(default=False)
    is_paid         = models.BooleanField(default=False)
    assigned_vehicle_type = models.CharField(max_length=10, blank=True, null=True, help_text='bus/train/flight')
    assigned_vehicle_id = models.PositiveIntegerField(null=True, blank=True)
    assigned_vehicle_name = models.CharField(max_length=200, blank=True)
    status          = models.CharField(max_length=20, choices=STATUS, default='booked')
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.parcel_id}: {self.origin} → {self.destination}"

    def progress_percentage(self):
        progress_map = {
            'booked': 10,
            'dropped_off': 40,
            'in_transit': 70,
            'arrived': 100,
            'collected': 100,
            'returned': 100,
        }
        return progress_map.get(self.status, 20)

    def calc_cost(self):
        return round(100 + float(self.weight_kg) * 50, 2)

class ParcelLog(models.Model):
    parcel     = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name='logs')
    status     = models.CharField(max_length=20)
    note       = models.TextField(blank=True)
    location   = models.CharField(max_length=100, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
