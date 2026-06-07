from types import SimpleNamespace
import datetime

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render

from apps.buses.models import Booking, Driver, Bus


def driver_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if request.user.role != 'driver':
            raise PermissionDenied('Only drivers may access the driver dashboard.')

        driver = None
        # Try linked profile first
        try:
            driver = request.user.driver_profile
        except Exception:
            driver = None

        # Try Driver record linked by user FK
        if not driver:
            try:
                driver = Driver.objects.get(user=request.user)
            except Driver.DoesNotExist:
                driver = None

        # Try matching by company + full name
        if not driver:
            try:
                full_name = (request.user.get_full_name() or '').strip()
                if full_name and request.user.company:
                    driver = Driver.objects.filter(company=request.user.company, name__iexact=full_name).first()
            except Exception:
                driver = None

        # Try matching by phone number
        if not driver:
            try:
                phone = getattr(request.user, 'phone_number', None)
                if phone and request.user.company:
                    driver = Driver.objects.filter(company=request.user.company, phone=phone).first()
            except Exception:
                driver = None

        # If still not found, try to infer driver from any Bus entries where the admin assigned a driver
        if not driver:
            try:
                # Match buses where the linked Driver has the same user or same name/phone
                qs = Bus.objects.select_related('driver', 'company')
                # prefer exact user match on driver.user
                bus_match = qs.filter(driver__user=request.user).first()
                if not bus_match:
                    full_name = (request.user.get_full_name() or '').strip()
                    phone = getattr(request.user, 'phone_number', None)
                    if full_name:
                        bus_match = qs.filter(driver__name__iexact=full_name).first()
                    if not bus_match and phone:
                        bus_match = qs.filter(driver__phone=phone).first()
                if bus_match and bus_match.driver:
                    driver = bus_match.driver
                elif bus_match:
                    # If bus has no Driver FK but admin stored name elsewhere, fallback to using bus company
                    driver = SimpleNamespace(
                        name=request.user.get_full_name() or request.user.username,
                        phone=getattr(request.user, 'phone_number', ''),
                        company=bus_match.company,
                    )
            except Exception:
                driver = driver or None

        # Final fallback: create an ad-hoc driver-like object carrying user's company
        if not driver:
            driver = SimpleNamespace(
                name=request.user.get_full_name() or request.user.username,
                phone=getattr(request.user, 'phone_number', ''),
                company=getattr(request.user, 'company', None),
            )

        request.driver = driver
        return view_func(request, *args, **kwargs)

    return _wrapped_view


@driver_required
def driver_dashboard(request):
    # Accept optional query params to filter the manifest
    selected_date = request.GET.get('travel_date')
    selected_bus_id = request.GET.get('bus')

    # Provide driver-assigned buses (handle both ORM Driver and fallback SimpleNamespace)
    driver_buses = []
    try:
        if isinstance(request.driver, Driver):
            driver_buses = list(Bus.objects.filter(driver=request.driver))
        else:
            # Try to find buses by matching driver name or phone
            name = getattr(request.driver, 'name', None)
            phone = getattr(request.driver, 'phone', None)
            company = getattr(request.driver, 'company', None)
            qs = Bus.objects.select_related('driver', 'company')
            if company:
                if name:
                    driver_buses = list(qs.filter(company=company, driver__name__iexact=name))
                if not driver_buses and phone:
                    driver_buses = list(qs.filter(company=company, driver__phone=phone))
            # fallback to any bus with a driver name match
            if not driver_buses and name:
                driver_buses = list(qs.filter(driver__name__icontains=name))
    except Exception:
        driver_buses = []

    # If driver has assigned buses and no bus selected, default to the first one
    if not selected_bus_id and driver_buses:
        selected_bus_id = str(driver_buses[0].id)

    # Default selected_date to today if not provided
    if not selected_date:
        selected_date = datetime.date.today().isoformat()

    # Query bookings by resolved bus id and date
    booking = None
    if selected_bus_id and selected_date:
        booking = Booking.objects.filter(
            bus_id=selected_bus_id,
            travel_date=selected_date,
            status='confirmed'
        ).order_by('-travel_date').first()
    elif selected_date:
        # any booking for driver's buses on that date
        bus_ids = [b.id for b in driver_buses] if driver_buses else []
        if bus_ids:
            booking = Booking.objects.filter(
                bus_id__in=bus_ids,
                travel_date=selected_date,
                status='confirmed'
            ).order_by('-travel_date').first()
        else:
            booking = Booking.objects.filter(
                travel_date=selected_date,
                status='confirmed'
            ).order_by('-travel_date').first()
    else:
        # recent confirmed booking for driver's buses
        bus_ids = [b.id for b in driver_buses] if driver_buses else []
        if bus_ids:
            booking = Booking.objects.filter(bus_id__in=bus_ids, status='confirmed').order_by('-travel_date').first()
        else:
            booking = Booking.objects.filter(status='confirmed').order_by('-travel_date').first()

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

    # Check if driver profile is properly linked
    is_linked, link_error = driver_profile_check(request.user)

    return render(request, 'driver/driver.html', {
        'driver': request.driver,
        'user': request.user,
        'credentials': credentials,
        'trip': trip,
        'passengers': passengers,
        'role_display': role_display,
        'company': company,
        'company_logo_url': company_logo_url,
        'driver_buses': driver_buses,
        'selected_date': selected_date,
        'selected_bus_id': selected_bus_id,
        'is_profile_linked': is_linked,
        'profile_link_error': link_error,
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


@driver_required
def manifest_api(request):
    """Return the confirmed bookings for a given bus and travel_date as JSON.

    Expects GET params: bus, travel_date
    """
    bus_id = request.GET.get('bus')
    travel_date = request.GET.get('travel_date')
    if not bus_id or not travel_date:
        return JsonResponse({'error': 'bus and travel_date required'}, status=400)

    qs = Booking.objects.filter(bus_id=bus_id, travel_date=travel_date, status='confirmed')
    data = []
    for b in qs:
        data.append({
            'id': b.id,
            'passenger_name': b.passenger_name,
            'seat': b.seat_number or '-',
            'phone': b.phone,
            'status': b.status,
        })
    return JsonResponse({'bookings': data})


@driver_required
def stop_passenger_tracking(request, pk):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST only')
    # In this simple implementation we only acknowledge the request.
    # Hook into real tracking cancellation logic if available.
    return JsonResponse({'status': 'tracking_stopped', 'passenger': pk})


def driver_profile_check(user):
    """Check if user's driver profile is a SimpleNamespace (unlinked) or a real Driver model."""
    try:
        if isinstance(user.driver_profile, Driver):
            return True, None  # is linked
    except Exception:
        pass
    # Try direct lookup
    try:
        driver = Driver.objects.get(user=user)
        return True, None
    except Driver.DoesNotExist:
        pass
    return False, "Profile not fully linked to driver record"  # is not linked


@driver_required
def link_driver_profile(request):
    """One-click endpoint to link the current User to a matching Driver record."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=400)
    
    # Try to find a matching Driver by name or phone
    driver_obj = None
    full_name = (request.user.get_full_name() or '').strip()
    phone = getattr(request.user, 'phone_number', None)
    company = getattr(request.user, 'company', None)
    
    # Search for Driver by company + name, or company + phone, or bus inference
    if company and full_name:
        driver_obj = Driver.objects.filter(company=company, name__iexact=full_name).first()
    if not driver_obj and company and phone:
        driver_obj = Driver.objects.filter(company=company, phone=phone).first()
    if not driver_obj:
        # Try via Bus inference
        qs = Bus.objects.select_related('driver').filter(driver__isnull=False)
        if full_name:
            qs_name = qs.filter(driver__name__iexact=full_name)
            if company:
                qs_name = qs_name.filter(company=company)
            bus_match = qs_name.first()
            if bus_match:
                driver_obj = bus_match.driver
        if not driver_obj and phone:
            qs_phone = qs.filter(driver__phone=phone)
            if company:
                qs_phone = qs_phone.filter(company=company)
            bus_match = qs_phone.first()
            if bus_match:
                driver_obj = bus_match.driver
    
    if driver_obj:
        # Link the User to the Driver
        driver_obj.user = request.user
        driver_obj.save()
        return JsonResponse({'status': 'linked', 'driver_id': driver_obj.id, 'driver_name': driver_obj.name})
    else:
        return JsonResponse({'error': 'No matching driver record found'}, status=404)