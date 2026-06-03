# apps/accounts/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):

        if not email:
            raise ValueError('The Email field must be set')

        email = self.normalize_email(email)

        # Automatically use email as username
        extra_fields.setdefault('username', email)

        user = self.model(
            email=email,
            **extra_fields
        )

        user.set_password(password)

        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:

            raise ValueError(
                'Superuser must have is_staff=True.'
            )

        if extra_fields.get('is_superuser') is not True:

            raise ValueError(
                'Superuser must have is_superuser=True.'
            )

        return self.create_user(
            email,
            password,
            **extra_fields
        )


class User(AbstractUser):

    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('bus_admin', 'Bus Admin'),
        ('train_admin', 'Train Admin'),
        ('flight_admin', 'Flight Admin'),
        ('driver', 'Driver'),
        ('technical_staff', 'Technical Staff'),
        ('passenger', 'Passenger'),
    )

    email = models.EmailField(
        unique=True
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='passenger'
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    wallet_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    redeemed_points = models.PositiveIntegerField(
        default=0
    )

    company = models.ForeignKey(
        'systemadmin.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees'
    )

    USERNAME_FIELD = 'email'

    REQUIRED_FIELDS = [
        'first_name',
        'last_name'
    ]

    objects = UserManager()

    def save(self, *args, **kwargs):

        # Always use email as username
        self.username = self.email

        # Remove company for admin/passenger
        if self.role in ['admin', 'passenger']:
            self.company = None

        super().save(*args, **kwargs)

    def __str__(self):

        full_name = f"{self.first_name} {self.last_name}".strip()

        if full_name:
            return f"{full_name} ({self.email})"

        return self.email