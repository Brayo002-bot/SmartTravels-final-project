from django.contrib import admin
from .models import Route, Pilot, Flight, Booking, Schedule


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = (
        'from_location',
        'to_location',
        'price',
        'first_class_price',
        'business_price',
        'economy_price',
        'company'
    )

    search_fields = (
        'from_location',
        'to_location',
    )

    fieldsets = (
        ('Location Details', {
            'fields': (
                'from_location',
                'to_location',
            )
        }),

        ('Pricing', {
            'fields': (
                'price',
                'first_class_price',
                'business_price',
                'economy_price',
            ),
            'description': 'Base price acts as fallback. Class prices override it.'
        }),

        ('Company', {
            'fields': (
                'company',
            )
        }),
    )


@admin.register(Pilot)
class PilotAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'phone',
        'company',
        'user',
    )

    search_fields = (
        'name',
        'phone',
    )

    list_filter = (
        'company',
    )


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = (
        'flight_number',
        'route',
        'pilot',
        'available_seats',
        'is_cargo',
        'company',
    )

    list_filter = (
        'route',
        'is_cargo',
        'company',
    )

    search_fields = (
        'flight_number',
    )


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'passenger_name',
        'phone',
        'flight',
        'route',
        'travel_date',
        'travel_time',
        'price',
        'status',
        'created_at',
    )

    list_filter = (
        'status',
        'travel_date',
    )

    search_fields = (
        'passenger_name',
        'phone',
        'booking_reference',
    )


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):

    # FIXED HERE
    list_display = (
        'flight',
        'travel_date',
        'travel_time',
        'price',
        'created_at',
    )

    list_filter = (
        'travel_date',
    )

    search_fields = (
        'flight__flight_number',
    )