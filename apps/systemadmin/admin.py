from django.contrib import admin
from .models import Company, SystemAdminRole, AuditLog, SystemSetting

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'transport_type', 'contact_email', 'is_active')
    list_filter = ('transport_type', 'is_active')
    search_fields = ('name', 'contact_email')
    ordering = ('name',)

@admin.register(SystemAdminRole)
class SystemAdminRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'timestamp')
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('user__username', 'details')
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)

@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'is_public')
    list_filter = ('is_public',)
    search_fields = ('key', 'description')
