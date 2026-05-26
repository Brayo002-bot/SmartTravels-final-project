from django.contrib import admin
from .models import (
    Company, SystemAdminRole, AuditLog, SystemSetting,
    SeatClass, VehicleLayout, Seat, SeatReservation, SeatBooking
)

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


# ===== SEAT MANAGEMENT ADMIN =====

@admin.register(SeatClass)
class SeatClassAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'transport_type', 'base_price', 'is_active')
    list_filter = ('transport_type', 'is_active')
    search_fields = ('display_name', 'name')
    ordering = ('transport_type', 'name')
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'transport_type', 'display_name', 'description')
        }),
        ('Pricing & Appearance', {
            'fields': ('base_price', 'color_code', 'icon')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )


@admin.register(VehicleLayout)
class VehicleLayoutAdmin(admin.ModelAdmin):
    list_display = ('template_name', 'vehicle_type', 'total_seats', 'company', 'is_template', 'created_at')
    list_filter = ('vehicle_type', 'is_template', 'is_active', 'company')
    search_fields = ('template_name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    ordering = ('-created_at',)
    fieldsets = (
        ('Basic Info', {
            'fields': ('company', 'vehicle_type', 'template_name', 'description', 'is_template')
        }),
        ('Layout Configuration', {
            'fields': ('total_seats', 'rows', 'columns', 'aisle_position', 'aisle_arrangement')
        }),
        ('Vehicle Features', {
            'fields': ('has_driver_cockpit', 'driver_location', 'has_doors', 'door_locations')
        }),
        ('Train Specific', {
            'fields': ('cabins',),
            'classes': ('collapse',)
        }),
        ('Flight Specific', {
            'fields': ('emergency_exits', 'galley_location', 'lavatory_locations'),
            'classes': ('collapse',)
        }),
        ('Data & Status', {
            'fields': ('layout_data', 'is_active', 'created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ('seat_number', 'content_type', 'vehicle_id', 'seat_class', 'status', 'price')
    list_filter = ('content_type', 'status', 'seat_class', 'is_extra_legroom', 'is_window')
    search_fields = ('seat_number', 'cabin_name')
    ordering = ('content_type', 'vehicle_id', 'seat_row', 'seat_column')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Vehicle & Location', {
            'fields': ('content_type', 'vehicle_id', 'seat_number', 'seat_row', 'seat_column')
        }),
        ('Cabin Info (Trains)', {
            'fields': ('cabin_id', 'cabin_name'),
            'classes': ('collapse',)
        }),
        ('Seat Details', {
            'fields': ('seat_class', 'price', 'status')
        }),
        ('Position & Features', {
            'fields': ('position_x', 'position_y', 'is_extra_legroom', 'is_window', 'is_aisle', 'is_emergency_exit_row')
        }),
        ('Hold Info', {
            'fields': ('held_until', 'held_by'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SeatReservation)
class SeatReservationAdmin(admin.ModelAdmin):
    list_display = ('user', 'seat', 'status', 'held_at', 'expires_at')
    list_filter = ('status', 'held_at', 'travel_date')
    search_fields = ('user__username', 'seat__seat_number', 'reservation_token')
    readonly_fields = ('held_at', 'released_at', 'reservation_token')
    ordering = ('-held_at',)


@admin.register(SeatBooking)
class SeatBookingAdmin(admin.ModelAdmin):
    list_display = ('booking_reference', 'passenger_name', 'seat', 'status', 'price_paid', 'is_checked_in')
    list_filter = ('status', 'content_type', 'is_checked_in', 'created_at')
    search_fields = ('booking_reference', 'passenger_name', 'seat__seat_number')
    readonly_fields = ('created_at', 'updated_at', 'checked_in_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Booking Info', {
            'fields': ('booking_reference', 'booking_id', 'content_type', 'status')
        }),
        ('Seat & Pricing', {
            'fields': ('seat', 'price_paid')
        }),
        ('Passenger Info', {
            'fields': ('passenger_name', 'passenger_phone', 'passenger_id', 'user')
        }),
        ('Check-in', {
            'fields': ('is_checked_in', 'checked_in_at', 'checked_in_by', 'qr_code'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
