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
