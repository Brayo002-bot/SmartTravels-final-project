from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render

def homepage(request):
    features = [
        {'icon':'📱','title':'M-Pesa Payments','desc':'Pay instantly via Safaricom M-Pesa STK Push. No card needed.','bg':'rgba(34,197,94,.15)'},
        {'icon':'📍','title':'Live GPS Tracking','desc':'Track your bus, train, or flight in real-time. Share tracking link with family.','bg':'rgba(37,99,235,.15)'},
        {'icon':'🎫','title':'QR-Code Tickets','desc':'Download PDF tickets with QR codes. Scan at boarding for instant verification.','bg':'rgba(245,158,11,.15)'},
        {'icon':'📦','title':'Parcel Delivery','desc':'Send parcels via existing routes. Track in real-time from sender to recipient.','bg':'rgba(139,92,246,.15)'},
        {'icon':'🪑','title':'Seat Selection','desc':'Dynamic seat maps for buses, trains, and flights. Choose your preferred seat.','bg':'rgba(239,68,68,.15)'},
        {'icon':'🤖','title':'AI Recommendations','desc':'Smart route suggestions based on your travel history and popular trends.','bg':'rgba(14,165,233,.15)'},
        {'icon':'📊','title':'Admin Analytics','desc':'Full dashboards for bus, train, and flight admins. Revenue, bookings, fleet reports.','bg':'rgba(16,185,129,.15)'},
        {'icon':'🆘','title':'Emergency SOS','desc':'One-tap emergency button alerts support and emergency contacts immediately.','bg':'rgba(239,68,68,.15)'},
        {'icon':'⭐','title':'Loyalty Rewards','desc':'Earn points on every booking. Bronze to Platinum tier rewards for frequent travelers.','bg':'rgba(245,158,11,.15)'},
    ]
    return render(request, 'index.html', {'features': features})

def privacy_policy(request):
    return render(request, 'base/privacy_policy.html')

def terms_conditions(request):
    return render(request, 'base/terms_and_conditions.html')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', homepage, name='homepage'),
    path('privacy-policy/', privacy_policy, name='privacy_policy'),
    path('terms-and-conditions/', terms_conditions, name='terms_conditions'),
    path('accounts/', include('apps.accounts.urls')),
    path('buses/', include('apps.buses.urls')),
    path('flights/', include('apps.flights.urls')),
    path('trains/', include('apps.trains.urls')),
    path('systemadmin/', include('apps.systemadmin.urls')),
    path('drivers/', include('apps.drivers.urls')),
    path('technical-staff/', include('apps.technical_staff.urls')),
    path('bookings/', include('apps.bookings.urls')),
    path('payments/', include('apps.payments.urls')),
    path('parcels/', include('apps.parcels.urls')),
    path('gps/', include('apps.gps.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('routes/', include('apps.routes.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
