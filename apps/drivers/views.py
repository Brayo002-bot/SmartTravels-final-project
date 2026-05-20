from types import SimpleNamespace

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render

from apps.buses.models import Booking, Driver


def driver_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if request.user.role != 'driver':
            raise PermissionDenied('Only drivers may access the driver dashboard.')

        try:
            driver = Driver.objects.get(user=request.user)
        except Driver.DoesNotExist:
            raise PermissionDenied('No driver profile is linked to this user account.')

        request.driver = driver
        return view_func(request, *args, **kwargs)

    return _wrapped_view


@driver_required
def driver_dashboard(request):
    booking = Booking.objects.filter(
        bus__driver=request.driver,
        status='confirmed'
    ).order_by('-travel_date').first()

    trip = None
    if booking:
        booked_seats = Booking.objects.filter(
            bus=booking.bus,
            travel_date=booking.travel_date,
            status='confirmed'
        ).count()
        trip = SimpleNamespace(
            route=str(booking.route),
            bus=str(booking.bus),
            departure_time=booking.travel_date,
            booked_seats=booked_seats,
        )

    return render(request, 'driver/driver.html', {
        'driver': request.driver,
        'trip': trip,
    })


@driver_required
def start_journey(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST only')
    return JsonResponse({'status': 'journey_started'})


@driver_required
def end_journey(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST only')
    return JsonResponse({'status': 'journey_ended'})


@driver_required
def update_location(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST only')

    return JsonResponse({'status': 'location_updated'})