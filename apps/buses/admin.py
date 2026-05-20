from django.contrib import admin

from .models import Bus, Booking, Driver, Route


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('from_location', 'to_location')
    search_fields = ('from_location', 'to_location')


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'user')
    search_fields = ('name', 'phone', 'user__email')


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ('bus_number', 'route', 'driver', 'available_seats')
    list_filter = ('route', 'driver')
    search_fields = ('bus_number',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('passenger_name', 'phone', 'bus', 'route', 'travel_date', 'status', 'created_at')
    list_filter = ('status', 'travel_date')
    search_fields = ('passenger_name', 'phone')
