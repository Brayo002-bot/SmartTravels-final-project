from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class SystemAdminRole(models.Model):
    ROLE_CHOICES = [
        ('super_admin', 'Super Administrator'),
        ('user_manager', 'User Manager'),
        ('content_manager', 'Content Manager'),
        ('finance_manager', 'Finance Manager'),
        ('support_manager', 'Support Manager'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='system_admin_role')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='super_admin')
    permissions = models.JSONField(default=dict, blank=True)  # Store specific permissions

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('permission_change', 'Permission Change'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"


class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)


class Company(models.Model):
    TRANSPORT_TYPE_CHOICES = [
        ('bus', 'Bus Company'),
        ('train', 'Train Company'),
        ('flight', 'Flight Company'),
    ]

    name = models.CharField(max_length=100, unique=True)
    transport_type = models.CharField(max_length=20, choices=TRANSPORT_TYPE_CHOICES)
    description = models.TextField(blank=True, help_text="Overall description of the company (visible to passengers)")
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    logo_image = models.ImageField(upload_to='company_logos/', blank=True, null=True, help_text="Company logo/image (visible to passengers)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_companies')

    class Meta:
        verbose_name_plural = "Companies"

    def __str__(self):
        return f"{self.name} ({self.get_transport_type_display()})"


class SeatLayoutHistory(models.Model):
    VEHICLE_TYPE_CHOICES = [
        ('bus', 'Bus'),
        ('train', 'Train'),
        ('flight', 'Flight'),
    ]

    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPE_CHOICES)
    vehicle_id = models.PositiveIntegerField(null=True, blank=True)
    config = models.JSONField(default=dict, blank=True)
    layout = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.vehicle_type.capitalize()} Layout #{self.id} ({self.created_at:%Y-%m-%d %H:%M})"


class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email


# ===== SEAT MANAGEMENT SYSTEM =====

class SeatClass(models.Model):
    """Defines seat classes (Economy, Business, First Class, VIP, etc.)"""
    SEAT_CLASS_TYPES = [
        ('economy', 'Economy'),
        ('business', 'Business'),
        ('first_class', 'First Class'),
        ('vip', 'VIP'),
        ('normal', 'Normal'),
        ('executive', 'Executive'),
        ('sleeper', 'Sleeper'),
    ]
    
    TRANSPORT_TYPES = [
        ('bus', 'Bus'),
        ('train', 'Train'),
        ('flight', 'Flight'),
    ]

    name = models.CharField(max_length=50, choices=SEAT_CLASS_TYPES)
    transport_type = models.CharField(max_length=20, choices=TRANSPORT_TYPES)
    display_name = models.CharField(max_length=100, help_text="Display name for passengers")
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    color_code = models.CharField(max_length=20, default='#2ecc71', help_text="Hex color for seat display")
    icon = models.CharField(max_length=50, default='seat', help_text="Icon class or emoji")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('name', 'transport_type')
        ordering = ['transport_type', 'name']
    
    def __str__(self):
        return f"{self.get_transport_type_display()} - {self.display_name}"


class VehicleLayout(models.Model):
    """Stores seat layout templates for vehicles (buses, trains, flights)"""
    VEHICLE_TYPES = [
        ('bus', 'Bus'),
        ('train', 'Train'),
        ('flight', 'Flight'),
    ]
    
    BUS_TEMPLATES = [
        ('14_seater', '14-Seater'),
        ('25_seater', '25-Seater'),
        ('33_seater', '33-Seater'),
        ('45_seater', '45-Seater'),
        ('49_seater', '49-Seater'),
        ('60_seater', '60-Seater'),
        ('custom', 'Custom'),
    ]
    
    AISLE_ARRANGEMENTS = [
        ('2x2', '2×2 (2 columns, 1 aisle)'),
        ('2x1_vip', '2×1 VIP (2 on left, 1 on right)'),
        ('3x2', '3×2 (3 columns, 1 aisle, 2 columns)'),
        ('3x3', '3×3 (3 columns, 1 aisle, 3 columns)'),
        ('sleeper', 'Sleeper (2 levels)'),
        ('custom', 'Custom Layout'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='vehicle_layouts')
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES)
    template_name = models.CharField(max_length=100, help_text="e.g., 'Dreamline VIP', '49-Seater Standard'")
    description = models.TextField(blank=True)
    
    # Layout configuration
    total_seats = models.PositiveIntegerField()
    rows = models.PositiveIntegerField(help_text="Number of rows")
    columns = models.PositiveIntegerField(help_text="Number of columns")
    aisle_position = models.PositiveIntegerField(default=1, help_text="Column index where aisle is located")
    aisle_arrangement = models.CharField(max_length=50, choices=AISLE_ARRANGEMENTS, default='2x2')
    
    # Vehicle-specific features
    has_driver_cockpit = models.BooleanField(default=True)
    driver_location = models.CharField(max_length=20, default='front', help_text="'front', 'left', 'right'")
    has_doors = models.PositiveIntegerField(default=2, help_text="Number of doors")
    door_locations = models.JSONField(default=list, blank=True, help_text="Door positions: [{'position': 'front', 'side': 'left'}]")
    
    # For trains: cabin/coach configuration
    cabins = models.JSONField(default=list, blank=True, help_text="Cabin info: [{'name': 'Cabin A', 'seats': 60, 'class': 'first_class'}]")
    
    # For flights: seat map configuration
    emergency_exits = models.PositiveIntegerField(default=0)
    galley_location = models.CharField(max_length=50, blank=True, help_text="Galley location on aircraft")
    lavatory_locations = models.JSONField(default=list, blank=True, help_text="Lavatory positions")
    
    # Layout data (JSON format for flexibility)
    layout_data = models.JSONField(default=dict, blank=True, help_text="Complete seat layout configuration")
    
    is_template = models.BooleanField(default=True, help_text="Reusable template flag")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_layouts')
    
    class Meta:
        unique_together = ('company', 'template_name', 'vehicle_type')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_vehicle_type_display()} - {self.template_name} ({self.total_seats} seats)"


class Seat(models.Model):
    """Individual seat records"""
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('reserved', 'Reserved/Held'),
        ('blocked', 'Blocked/Unavailable'),
    ]
    
    # Link to vehicle (polymorphic relationship)
    content_type = models.CharField(max_length=20, choices=[('bus', 'Bus'), ('train', 'Train'), ('flight', 'Flight')])
    vehicle_id = models.PositiveIntegerField()
    
    # Seat identification
    seat_number = models.CharField(max_length=20, help_text="e.g., '1A', 'A-01', '12'")
    seat_row = models.PositiveIntegerField(help_text="Row number")
    seat_column = models.CharField(max_length=10, help_text="Column letter (A, B, C, etc.)")
    
    # For trains
    cabin_id = models.CharField(max_length=50, blank=True, help_text="Cabin/Coach identifier")
    cabin_name = models.CharField(max_length=100, blank=True, help_text="Cabin/Coach name")
    
    # Seat characteristics
    seat_class = models.ForeignKey(SeatClass, on_delete=models.PROTECT, related_name='seats')
    position_x = models.PositiveIntegerField(help_text="X coordinate for UI rendering")
    position_y = models.PositiveIntegerField(help_text="Y coordinate for UI rendering")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Special features
    is_extra_legroom = models.BooleanField(default=False)
    is_window = models.BooleanField(default=False)
    is_aisle = models.BooleanField(default=False)
    is_emergency_exit_row = models.BooleanField(default=False)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    held_until = models.DateTimeField(null=True, blank=True, help_text="Reservation hold expiration time")
    held_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='held_seats')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('content_type', 'vehicle_id', 'seat_number')
        indexes = [
            models.Index(fields=['content_type', 'vehicle_id', 'status']),
        ]
        ordering = ['seat_row', 'seat_column']
    
    def __str__(self):
        vehicle_type = self.get_content_type_display() if hasattr(self, 'get_content_type_display') else self.content_type
        return f"{vehicle_type.capitalize()} {self.vehicle_id} - Seat {self.seat_number} ({self.status})"
    
    def is_available_for_booking(self):
        """Check if seat is available for booking"""
        if self.status == 'available':
            return True
        if self.status == 'reserved' and self.held_until and self.held_until < models.F('held_until'):
            # Hold has expired
            return True
        return False


class SeatReservation(models.Model):
    """Temporary seat holds during checkout"""
    STATUS_CHOICES = [
        ('active', 'Active Hold'),
        ('confirmed', 'Confirmed (Booking Created)'),
        ('released', 'Released'),
        ('expired', 'Expired'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='seat_reservations')
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE, related_name='reservations')
    
    # Reservation details
    reservation_token = models.CharField(max_length=100, unique=True, help_text="Unique token for this hold")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    hold_duration_minutes = models.PositiveIntegerField(default=10, help_text="Minutes to hold seat")
    held_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    # Booking context
    travel_date = models.DateField()
    travel_time = models.TimeField(null=True, blank=True)
    
    # Release reason
    release_reason = models.CharField(max_length=200, blank=True, help_text="Why the reservation was released")
    released_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-held_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Hold: {self.user.username} - Seat {self.seat.seat_number} ({self.status})"
    
    def is_expired(self):
        """Check if reservation has expired"""
        from django.utils import timezone
        return timezone.now() > self.expires_at


class SeatBooking(models.Model):
    """Links seats to actual bookings"""
    BOOKING_STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('checked_in', 'Checked In'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Link to booking (polymorphic - can be bus, train, or flight booking)
    content_type = models.CharField(max_length=20, choices=[('bus', 'Bus'), ('train', 'Train'), ('flight', 'Flight')])
    booking_id = models.PositiveIntegerField()
    
    seat = models.ForeignKey(Seat, on_delete=models.PROTECT, related_name='bookings')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='seat_bookings')
    
    # Booking details
    booking_reference = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=BOOKING_STATUS, default='pending')
    price_paid = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Passenger info
    passenger_name = models.CharField(max_length=255)
    passenger_phone = models.CharField(max_length=50, blank=True)
    passenger_id = models.CharField(max_length=50, blank=True, help_text="Passport/ID for verification")
    
    # Check-in tracking
    is_checked_in = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                      related_name='seat_checkins')
    
    # QR code for verification
    qr_code = models.CharField(max_length=500, blank=True, help_text="QR code data")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('seat', 'booking_id', 'content_type')
        indexes = [
            models.Index(fields=['booking_reference']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Booking {self.booking_reference} - Seat {self.seat.seat_number}"
