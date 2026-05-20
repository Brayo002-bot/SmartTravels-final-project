from django.contrib import admin

from .models import TechnicalStaff


@admin.register(TechnicalStaff)
class TechnicalStaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'user', 'phone', 'created_at')
    list_filter = ('company',)
    search_fields = ('name', 'phone', 'company__name', 'user__email')
