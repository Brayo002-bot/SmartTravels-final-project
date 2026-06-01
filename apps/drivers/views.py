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

        driver = None
        try:
            driver = request.user.driver_profile
        except Exception:
            pass

        if not driver:
            try:
                driver = Driver.objects.get(user=request.user)
            except Driver.DoesNotExist:
                # Fallback to a temporary driver object if the user is a driver but profile isn't linked.
                driver = SimpleNamespace(
                    name=request.user.get_full_name() or request.user.username,
                    phone=getattr(request.user, 'phone_number', ''),
                    company=None,
                )

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

    # Build passenger manifest for the current trip (if any)
    passengers = []
    if booking:
        booking_qs = Booking.objects.filter(
            bus=booking.bus,
            travel_date=booking.travel_date,
            status='confirmed'
        )
        for b in booking_qs:
            passengers.append(SimpleNamespace(
                id=b.id,
                name=b.passenger_name,
                seat=b.seat_number or '-',
                phone=b.phone,
            ))

    # Provide a role display string for template use (user carries role)
    role_display = getattr(request.user, 'get_role_display', None)
    if callable(role_display):
        role_display = request.user.get_role_display()
    else:
        role_display = getattr(request.user, 'role', '')

    # Get driver company and details
    company = getattr(request.driver, 'company', None)
    company_logo_url = None
    if company and hasattr(company, 'logo_image') and company.logo_image:
        try:
            company_logo_url = company.logo_image.url
        except Exception:
            company_logo_url = None

    # Prepare driver credentials object with all available fields
    driver_name = getattr(request.driver, 'name', None) or request.user.get_full_name() or request.user.username
    driver_phone = getattr(request.driver, 'phone', None) or getattr(request.user, 'phone_number', '')
    credentials = {
        'driver_name': driver_name,
        'driver_phone': driver_phone,
        'user_email': request.user.email,
        'user_first_name': request.user.first_name,
        'user_last_name': request.user.last_name,
        'user_phone': request.user.phone_number,
        'username': request.user.username,
    }

    return render(request, 'driver/driver.html', {
        'driver': request.driver,
        'user': request.user,
        'credentials': credentials,
        'trip': trip,
        'passengers': passengers,
        'role_display': role_display,
        'company': company,
        'company_logo_url': company_logo_url,
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