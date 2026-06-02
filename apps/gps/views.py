from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import PermissionDenied
from .models import GPSPoint

@login_required
def live_tracking(request):
    # Render the passenger-facing tracking page so the sidebar 'Track Journey'
    # link opens the `passenger_tracking.html` template (includes passenger sidebar).
    context = {
        'vehicle_type': None,
        'vehicle_id': None,
        'latest_point': None,
        'has_tracking': False,
        'booking': None,
    }
    return render(request, 'tracking/passenger_tracking.html', context)

@login_required
def passenger_track_journey(request, vehicle_type=None, vehicle_id=None, booking_reference=None):
    """Allow passengers to track a specific vehicle's journey"""
    if request.user.role != 'passenger':
        raise PermissionDenied
    
    booking = None
    latest_point = None
    
    # If booking reference is provided, look up the booking
    if booking_reference:
        from apps.buses.models import Booking as BusBooking
        from apps.trains.models import Booking as TrainBooking
        from apps.flights.models import Booking as FlightBooking
        
        # Try to find booking in all models
        booking = (BusBooking.objects.filter(booking_reference=booking_reference).first() or
                  TrainBooking.objects.filter(booking_reference=booking_reference).first() or
                  FlightBooking.objects.filter(booking_reference=booking_reference).first())
        
        if booking:
            # Determine vehicle type and ID
            if hasattr(booking, 'bus'):
                vehicle_type = 'bus'
                vehicle_id = booking.bus.id
            elif hasattr(booking, 'train'):
                vehicle_type = 'train'
                vehicle_id = booking.train.id
            elif hasattr(booking, 'flight'):
                vehicle_type = 'flight'
                vehicle_id = booking.flight.id
            # Attach company and logo for the booking (if available)
            transport = getattr(booking, 'bus', None) or getattr(booking, 'train', None) or getattr(booking, 'flight', None)
            company = getattr(transport, 'company', None) if transport else None
            company_logo_url = None
            try:
                if company and getattr(company, 'logo_image', None):
                    company_logo_url = company.logo_image.url
            except Exception:
                company_logo_url = None
            # expose on booking for template convenience
            booking.company = company
            booking.company_name = company.name if company else None
            booking.company_logo_url = company_logo_url
    
    # Get the latest GPS point for this vehicle
    if vehicle_type and vehicle_id:
        latest_point = GPSPoint.objects.filter(
            vehicle_id=vehicle_id,
            vehicle_type=vehicle_type
        ).first()
    
    context = {
        'vehicle_type': vehicle_type,
        'vehicle_id': vehicle_id,
        'latest_point': latest_point,
        'has_tracking': latest_point is not None,
        'booking': booking,
        'company': getattr(booking, 'company', None),
        'company_logo_url': getattr(booking, 'company_logo_url', None),
    }
    
    return render(request, 'tracking/passenger_tracking.html', context)

@csrf_exempt
@login_required
def update_gps(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        GPSPoint.objects.create(
            driver=request.user,
            vehicle_id=data.get('vehicle_id', 0),
            vehicle_type=data.get('vehicle_type', 'bus'),
            latitude=data['lat'],
            longitude=data['lng'],
            speed_kmh=data.get('speed', 0),
        )
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'error': 'POST required'}, status=405)

@login_required
def get_vehicle_location(request, vehicle_type, vehicle_id):
    point = GPSPoint.objects.filter(vehicle_id=vehicle_id, vehicle_type=vehicle_type).first()
    if point:
        return JsonResponse({'lat': float(point.latitude), 'lng': float(point.longitude),
                             'speed': float(point.speed_kmh), 'time': point.recorded_at.isoformat()})
    return JsonResponse({'error': 'No GPS data'}, status=404)
