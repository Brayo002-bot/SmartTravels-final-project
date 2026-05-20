from django.contrib import admin
from .models import Parcel, ParcelLog

class ParcelLogInline(admin.TabularInline):
    model = ParcelLog
    extra = 0
    readonly_fields = ('timestamp',)

@admin.register(Parcel)
class ParcelAdmin(admin.ModelAdmin):
    list_display = ('parcel_id', 'sender_name', 'recipient_name', 'origin', 'destination', 'status', 'shipping_cost', 'created_at')
    list_filter = ('status', 'category', 'is_paid')
    search_fields = ('parcel_id', 'sender_name', 'recipient_name', 'recipient_phone')
    inlines = [ParcelLogInline]
