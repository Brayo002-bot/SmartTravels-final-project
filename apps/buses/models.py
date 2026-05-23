from django.conf import settings
from django.db import models


class Route(models.Model):
    from_location = models.CharField(max_length=255)
    to_location = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Price per ticket for this route")
    company = models.ForeignKey(
        'systemadmin.Company',
        on_delete=models.CASCADE,
        related_name='bus_routes',
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.from_location} → {self.to_location}"


class Driver(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='driver_profile',
    )
    company = models.ForeignKey(
        'systemadmin.Company',
        on_delete=models.CASCADE,
        related_name='bus_drivers',
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name


class Bus(models.Model):
    bus_number = models.CharField(max_length=100, unique=True)
    number_plate = models.CharField(max_length=20, blank=True, null=True, help_text="Vehicle registration number plate")
    description = models.TextField(blank=True, null=True, help_text="Brief description of the bus (visible to passengers)")
    is_cargo = models.BooleanField(default=False, help_text="Mark this vehicle as cargo only (not visible to passenger bookings)")
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='buses')
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='buses')
    company = models.ForeignKey(
        'systemadmin.Company',
        on_delete=models.CASCADE,
        related_name='buses',
        null=True,
        blank=True,
    )
    vip_seats = models.PositiveIntegerField(default=5)
    normal_seats = models.PositiveIntegerField(default=35)
    available_seats = models.PositiveIntegerField(default=40)

    def save(self, *args, **kwargs):
        if self.is_cargo:
            self.available_seats = 0
        else:
            self.available_seats = self.vip_seats + self.normal_seats
        super().save(*args, **kwargs)

    def __str__(self):
        return self.bus_number


class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ]

    passenger_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='bookings')
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='bookings')
    travel_date = models.DateField()
    travel_time = models.TimeField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    seat_number = models.CharField(max_length=10, blank=True, null=True)
    booking_reference = models.CharField(max_length=20, unique=True, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    boarded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Booking {self.booking_reference or self.id} - {self.passenger_name}"


class Schedule(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='schedules')
    travel_date = models.DateField()
    travel_time = models.TimeField()
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bus} schedule on {self.travel_date} at {self.travel_time}"
