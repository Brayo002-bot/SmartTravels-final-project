from django.contrib import admin
from .models import Route, Conductor, Train, Booking, Schedule


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


@admin.register(Conductor)
class ConductorAdmin(admin.ModelAdmin):
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


@admin.register(Train)
class TrainAdmin(admin.ModelAdmin):
    list_display = (
        'train_number',
        'route',
        'conductor',
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
        'train_number',
    )


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'passenger_name',
        'phone',
        'train',
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
        'train',
        'travel_date',
        'travel_time',
        'price',
        'created_at',
    )

    list_filter = (
        'travel_date',
    )

    search_fields = (
        'train__train_number',
    )