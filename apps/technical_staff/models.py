from django.conf import settings
from django.db import models


class TechnicalStaff(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=50, blank=True)
    company = models.ForeignKey(
        'systemadmin.Company',
        on_delete=models.CASCADE,
        related_name='technical_staff',
        null=True,
        blank=True,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='technical_staff_profile',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Technical Staff'
        verbose_name_plural = 'Technical Staff'
        ordering = ['name']

    def __str__(self):
        return self.name
