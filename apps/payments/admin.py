from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('booking_reference','booking_type','passenger','amount','method','status','mpesa_code','created_at')
    list_filter = ('status','method','booking_type')
    search_fields = ('booking_reference','mpesa_code','passenger__username')
    readonly_fields = ('created_at','completed_at')
