from datetime import date

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.gps.models import GPSPoint
from apps.parcels.models import Parcel, ParcelLog
from apps.systemadmin.models import SeatLayoutHistory
from apps.systemadmin.seat_layout import generate_seat_layout, normalize_class_counts
from .models import Bus, Booking, Driver, Route, Schedule

User = get_user_model()


def bus_admin_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.role != 'bus_admin' or not request.user.company or request.user.company.transport_type != 'bus':
            raise PermissionDenied('You do not have access to the bus admin section.')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@bus_admin_required
def bus_dashboard(request):
    company = request.user.company
    total_routes = Route.objects.filter(company=company).count()
    total_buses = Bus.objects.filter(company=company).count()
    todays_bookings = Booking.objects.filter(travel_date=timezone.localdate(), bus__company=company).count()
    todays_schedules = Schedule.objects.filter(travel_date=timezone.localdate(), bus__company=company).count()
    pending_reports = Booking.objects.filter(status='pending', bus__company=company).count()
    recent_bookings = Booking.objects.filter(bus__company=company).order_by('-created_at')[:5]

    return render(request, 'bus_admin/dashboard.html', {
        'total_routes': total_routes,
        'total_buses': total_buses,
        'todays_bookings': todays_bookings,
        'todays_schedules': todays_schedules,
        'pending_reports': pending_reports,
        'recent_bookings': recent_bookings,
    })


@bus_admin_required
def add_route(request):
    company = request.user.company
    if request.method == 'POST':
        from_location = request.POST.get('from_location', '').strip()
        to_location = request.POST.get('to_location', '').strip()
        price = request.POST.get('price', 0)
        try:
            price = float(price) if price else 0
        except ValueError:
            price = 0
        if from_location and to_location:
            Route.objects.create(
                from_location=from_location,
                to_location=to_location,
                price=price,
                company=company,
            )
            return redirect('bus_add_route')

    routes = Route.objects.filter(company=company).order_by('from_location', 'to_location')
    return render(request, 'bus_admin/add_route.html', {'routes': routes})


@bus_admin_required
def edit_route(request, route_id):
    company = request.user.company
    route = get_object_or_404(Route, id=route_id, company=company)
    if request.method == 'POST':
        route.from_location = request.POST.get('from_location', '').strip()
        route.to_location = request.POST.get('to_location', '').strip()
        route.price = float(request.POST.get('price', 0) or 0)
        route.save()
        messages.success(request, 'Route updated successfully.')
        return redirect('bus_add_route')
    return render(request, 'bus_admin/edit_route.html', {'route': route})


@bus_admin_required
def delete_route(request, route_id):
    company = request.user.company
    route = get_object_or_404(Route, id=route_id, company=company)
    route.delete()
    messages.success(request, 'Route deleted successfully.')
    return redirect('bus_add_route')


@bus_admin_required
def reports(request):
    company = request.user.company
    total_buses = Bus.objects.filter(company=company).count()
    total_drivers = Driver.objects.filter(company=company).count()
    total_routes = Route.objects.filter(company=company).count()
    total_bookings = Booking.objects.filter(bus__company=company).count()
    bookings = Booking.objects.filter(bus__company=company).select_related('bus', 'route').order_by('-created_at')[:50]
    buses = Bus.objects.filter(company=company).select_related('route', 'driver').all()

    return render(request, 'bus_admin/reports.html', {
        'total_buses': total_buses,
        'total_drivers': total_drivers,
        'total_routes': total_routes,
        'total_bookings': total_bookings,
        'bookings': bookings,
        'buses': buses,
    })


@bus_admin_required
def booking(request):
    company = request.user.company
    routes = Route.objects.filter(company=company)
    buses = Bus.objects.filter(company=company, available_seats__gt=0)
    bookings = Booking.objects.filter(bus__company=company).select_related('bus', 'route').order_by('-created_at')

    if request.method == 'POST':
        passenger_name = request.POST.get('passenger_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        route_id = request.POST.get('route')
        bus_id = request.POST.get('bus')
        travel_date = request.POST.get('travel_date')
        seat_number = request.POST.get('seat_number', '').strip()

        if passenger_name and phone and route_id and bus_id and travel_date:
            bus = get_object_or_404(Bus, id=bus_id, company=company)
            route = get_object_or_404(Route, id=route_id, company=company)

            if bus.available_seats > 0:
                Booking.objects.create(
                    passenger_name=passenger_name,
                    phone=phone,
                    bus=bus,
                    route=route,
                    travel_date=travel_date,
                    seat_number=seat_number if seat_number else None,
                    status='confirmed',
                )
                bus.available_seats -= 1
                bus.save()
                messages.success(request, f'Booking confirmed for {passenger_name}' + (f' at seat {seat_number}' if seat_number else '') + '.')
                return redirect('bus_booking')

    return render(request, 'bus_admin/booking.html', {
        'routes': routes,
        'buses': buses,
        'bookings': bookings,
    })


@bus_admin_required
def get_available_seats(request):
    bus_id = request.GET.get('bus_id')
    travel_date = request.GET.get('travel_date')
    if not bus_id:
        return JsonResponse({'error': 'Bus ID required'}, status=400)

    company = request.user.company
    bus = get_object_or_404(Bus, id=bus_id, company=company)

    # Get booked seats for this bus on the provided travel_date
    booked_qs = Booking.objects.filter(bus=bus)
    if travel_date:
        booked_qs = booked_qs.filter(travel_date=travel_date)
    booked_seats = list(booked_qs.exclude(seat_number__isnull=True).exclude(seat_number='').values_list('seat_number', flat=True))

    try:
        counts = {
            'vip_seats': bus.vip_seats,
            'normal_seats': bus.normal_seats,
        }
        layout = generate_seat_layout('bus', counts, booked_numbers=booked_seats, vehicle_id=bus.id)
        return JsonResponse(layout)
    except Exception:
        # Fallback: return simple seat numbers
        available = []
        for i in range(1, (bus.vip_seats or 0) + (bus.normal_seats or 0) + 1):
            seat_str = str(i)
            if seat_str not in booked_seats:
                available.append(seat_str)
        return JsonResponse({'available_seats': available})


@bus_admin_required
def schedule(request):
    company = request.user.company
    selected_date = request.GET.get('date')
    try:
        selected_date = date.fromisoformat(selected_date) if selected_date else timezone.localdate()
    except ValueError:
        selected_date = timezone.localdate()

    schedules = Schedule.objects.filter(travel_date=selected_date, bus__company=company).select_related('bus', 'bus__route').order_by('travel_time')
    buses = Bus.objects.filter(company=company)

    if request.method == 'POST':
        bus_id = request.POST.get('bus')
        travel_date = request.POST.get('travel_date')
        travel_time = request.POST.get('travel_time')

        if bus_id and travel_date and travel_time:
            bus = get_object_or_404(Bus, id=bus_id, company=company)
            Schedule.objects.create(
                bus=bus,
                travel_date=travel_date,
                travel_time=travel_time,
                price=bus.route.price,
            )
            return redirect('/buses/schedule/')

    return render(request, 'bus_admin/schedule.html', {
        'schedules': schedules,
        'buses': buses,
        'selected_date': selected_date,
    })


@bus_admin_required
def add_driver(request):
    company = request.user.company
    if request.method == 'POST':
        if 'name' in request.POST:
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            if name and phone:
                Driver.objects.create(name=name, phone=phone, company=company)
                messages.success(request, 'Driver added successfully.')
                return redirect('add_driver')

        if 'assign_login' in request.POST:
            driver_id = request.POST.get('driver_id')
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '').strip()

            driver = get_object_or_404(Driver, id=driver_id, company=company)
            if driver.user is not None:
                messages.warning(request, 'This driver already has login credentials.')
                return redirect('add_driver')

            if not email or not password:
                messages.error(request, 'Please provide both email and password to assign login credentials.')
                return redirect('add_driver')

            if User.objects.filter(username=email).exists():
                messages.error(request, 'A user account with that email already exists.')
                return redirect('add_driver')

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                role='driver'
            )
            driver.user = user
            driver.save()

            messages.success(request, f'Login created for {driver.name}.')
            return redirect('add_driver')

    drivers = Driver.objects.filter(company=company).order_by('name')
    return render(request, 'bus_admin/add_driver.html', {'drivers': drivers})


@bus_admin_required
def bus_seat_preview(request):
    total_passengers = int(request.GET.get('total_passengers') or 0)
    vip_percent = float(request.GET.get('vip_percent') or request.GET.get('vip_share') or 0)
    vip_seats = int(request.GET.get('vip_seats') or 0)
    normal_seats = int(request.GET.get('normal_seats') or 0)

    if total_passengers > 0:
        vip_seats = int(round(total_passengers * (vip_percent / 100)))
        normal_seats = total_passengers - vip_seats

    layout = generate_seat_layout(
        'bus',
        {'vip_seats': vip_seats, 'normal_seats': normal_seats},
    )
    return JsonResponse(layout)


@bus_admin_required
def generate_bus_layout(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    company = request.user.company
    bus_id = request.POST.get('bus_id')
    vip_seats = int(request.POST.get('vip_seats') or 0)
    normal_seats = int(request.POST.get('normal_seats') or 0)

    if not bus_id:
        return JsonResponse({'error': 'Missing bus_id'}, status=400)

    bus = get_object_or_404(Bus, id=bus_id, company=company)
    layout = generate_seat_layout(
        'bus',
        {'vip_seats': vip_seats, 'normal_seats': normal_seats},
        vehicle_id=bus.id,
    )
    SeatLayoutHistory.objects.create(
        vehicle_type='bus',
        vehicle_id=bus.id,
        config={'vip_seats': vip_seats, 'normal_seats': normal_seats},
        layout=layout,
    )

    return JsonResponse(layout)


@bus_admin_required
def add_buses(request):
    company = request.user.company
    if request.method == 'POST':
        bus_number = request.POST.get('bus_number', '').strip()
        number_plate = request.POST.get('number_plate', '').strip()
        description = request.POST.get('description', '').strip()
        route_id = request.POST.get('route')
        driver_id = request.POST.get('driver')
        vehicle_type = request.POST.get('vehicle_type', 'passenger')
        is_cargo = vehicle_type == 'cargo'
        total_passengers = int(request.POST.get('total_passengers') or 0)
        vip_seats = int(request.POST.get('vip_seats') or 0)
        normal_seats = int(request.POST.get('normal_seats') or 0)

        if not is_cargo:
            if vip_seats + normal_seats <= 0 and total_passengers > 0:
                vip_seats = int(round(total_passengers * 0.15))
                normal_seats = total_passengers - vip_seats
        else:
            vip_seats = 0
            normal_seats = 0

        if bus_number and route_id and driver_id:
            route = get_object_or_404(Route, id=route_id, company=company)
            driver = get_object_or_404(Driver, id=driver_id, company=company)
            bus = Bus.objects.create(
                bus_number=bus_number,
                number_plate=number_plate or None,
                description=description or None,
                is_cargo=is_cargo,
                route=route,
                driver=driver,
                company=company,
                vip_seats=vip_seats,
                normal_seats=normal_seats,
            )
            if not is_cargo:
                layout = generate_seat_layout(
                    'bus',
                    {'vip_seats': vip_seats, 'normal_seats': normal_seats},
                    vehicle_id=bus.id,
                )
                SeatLayoutHistory.objects.create(
                    vehicle_type='bus',
                    vehicle_id=bus.id,
                    config={
                        'total_passengers': total_passengers,
                        'vip_seats': vip_seats,
                        'normal_seats': normal_seats,
                    },
                    layout=layout,
                )
            return redirect('add_buses')

    routes = Route.objects.filter(company=company)
    drivers = Driver.objects.filter(company=company)
    buses = Bus.objects.filter(company=company).select_related('route', 'driver')
    bus_ids = list(buses.values_list('id', flat=True))
    seat_layout_histories = SeatLayoutHistory.objects.filter(vehicle_type='bus', vehicle_id__in=bus_ids)[:10]
    return render(request, 'bus_admin/add_buses.html', {
        'routes': routes,
        'drivers': drivers,
        'buses': buses,
        'seat_layout_histories': seat_layout_histories,
    })


@bus_admin_required
def cargo(request):
    company = request.user.company
    routes = Route.objects.filter(company=company).order_by('from_location', 'to_location')
    cargo_items = Parcel.objects.filter(sender=request.user).order_by('-created_at')
    shipments_count = cargo_items.count()
    aggregates = cargo_items.aggregate(total_weight=Sum('weight_kg'), total_value=Sum('declared_value'))
    total_weight = float(aggregates['total_weight'] or 0)
    total_value = float(aggregates['total_value'] or 0)

    if request.method == 'POST':
        sender_name = request.POST.get('sender_name', '').strip() or str(request.user)
        sender_phone = request.POST.get('sender_phone', '').strip() or request.user.phone_number or ''
        recipient_name = request.POST.get('recipient_name', '').strip()
        recipient_phone = request.POST.get('recipient_phone', '').strip()
        origin = request.POST.get('origin', '').strip()
        destination = request.POST.get('destination', '').strip()
        category = request.POST.get('category', 'other')
        description = request.POST.get('description', '').strip()
        weight_kg = float(request.POST.get('weight_kg') or 1)
        declared_value = float(request.POST.get('declared_value') or 0)
        is_fragile = request.POST.get('is_fragile') == 'on'
        is_paid = request.POST.get('is_paid') == 'on'
        notes = request.POST.get('notes', '').strip()

        if sender_name and sender_phone and recipient_name and recipient_phone and origin and destination:
            parcel = Parcel.objects.create(
                sender=request.user,
                sender_name=sender_name,
                sender_phone=sender_phone,
                recipient_name=recipient_name,
                recipient_phone=recipient_phone,
                origin=origin,
                destination=destination,
                category=category,
                description=description,
                weight_kg=weight_kg,
                declared_value=declared_value,
                shipping_cost=0,
                is_fragile=is_fragile,
                is_paid=is_paid,
                status='booked',
                notes=notes,
            )
            # assign vehicle if provided
            vehicle_id = request.POST.get('vehicle_id')
            if vehicle_id:
                try:
                    v = Bus.objects.filter(id=vehicle_id, company=company).first()
                    if v:
                        parcel.assigned_vehicle_type = 'bus'
                        parcel.assigned_vehicle_id = v.id
                        parcel.assigned_vehicle_name = str(v)
                        parcel.save(update_fields=['assigned_vehicle_type','assigned_vehicle_id','assigned_vehicle_name'])
                except Exception:
                    pass
            parcel.shipping_cost = parcel.calc_cost()
            parcel.save(update_fields=['shipping_cost'])
            ParcelLog.objects.create(
                parcel=parcel,
                status='booked',
                location=origin,
                updated_by=request.user,
                note='Cargo shipment created by admin.',
            )
            messages.success(request, f'Cargo shipment {parcel.parcel_id} created successfully.')
            return redirect('bus_cargo')
        else:
            messages.error(request, 'Please complete sender, recipient, origin and destination information.')

    return render(request, 'shared/admin_cargo.html', {
        'routes': routes,
        'cargo_items': cargo_items,
        'shipments_count': shipments_count,
        'total_weight': total_weight,
        'total_value': total_value,
        'sidebar_template': 'bus_admin/sidebar.html',
        'page_title': 'Bus Cargo Shipments',
        'page_description': 'Create cargo and parcel shipments for your bus routes.',
        'transport_label': 'Bus',
        'category_choices': Parcel.CATEGORY,
        'vehicles': Bus.objects.filter(company=company, is_cargo=True),
    })



@bus_admin_required
def traffic(request):
    company = request.user.company
    bus_ids = list(Bus.objects.filter(company=company).values_list('id', flat=True))
    latest_points = GPSPoint.objects.filter(vehicle_type='bus', vehicle_id__in=bus_ids).select_related('driver').order_by('-recorded_at')[:20]
    avg_speed = latest_points.aggregate(avg_speed=Avg('speed_kmh'))['avg_speed'] or 0
    active_vehicles = latest_points.values('vehicle_id').distinct().count()
    if avg_speed < 25:
        traffic_status = 'Heavy congestion'
    elif avg_speed < 50:
        traffic_status = 'Moderate traffic'
    else:
        traffic_status = 'Clear roads'

    return render(request, 'shared/admin_traffic.html', {
        'latest_gps': latest_points,
        'avg_speed': avg_speed,
        'active_vehicles': active_vehicles,
        'traffic_status': traffic_status,
        'sidebar_template': 'bus_admin/sidebar.html',
        'page_title': 'Bus Traffic Centre',
        'page_description': 'Monitor live bus GPS updates and route traffic conditions.',
        'transport_label': 'Bus',
    })


@bus_admin_required
def company_profile(request):
    """View and edit company profile"""
    from django.contrib.auth import get_user_model
    from apps.systemadmin.models import Company
    User = get_user_model()
    
    company = request.user.company
    
    if request.method == 'POST':
        company.description = request.POST.get('description', '').strip() or company.description
        company.contact_phone = request.POST.get('contact_phone', '').strip() or company.contact_phone
        company.contact_email = request.POST.get('contact_email', '').strip() or company.contact_email
        company.address = request.POST.get('address', '').strip() or company.address
        
        # Handle logo deletion
        if request.POST.get('delete_logo') == 'on':
            if company.logo_image:
                company.logo_image.delete()
                company.logo_image = None
        # Handle file upload
        elif 'logo_image' in request.FILES:
            company.logo_image = request.FILES['logo_image']
        
        company.updated_by = request.user
        company.save()
        messages.success(request, 'Company profile updated successfully.')
        return redirect('bus_company_profile')
    
    return render(request, 'bus_admin/company_profile.html', {'company': company})


@bus_admin_required
def edit_bus(request, bus_id):
    """Edit bus details"""
    company = request.user.company
    bus = get_object_or_404(Bus, id=bus_id, company=company)
    
    if request.method == 'POST':
        bus.bus_number = request.POST.get('bus_number', '').strip()
        bus.number_plate = request.POST.get('number_plate', '').strip() or None
        bus.description = request.POST.get('description', '').strip() or None
        route_id = request.POST.get('route')
        driver_id = request.POST.get('driver')
        
        if route_id:
            bus.route = get_object_or_404(Route, id=route_id, company=company)
        if driver_id:
            bus.driver = get_object_or_404(Driver, id=driver_id, company=company)
        
        bus.save()
        messages.success(request, 'Bus updated successfully.')
        return redirect('add_buses')
    
    routes = Route.objects.filter(company=company)
    drivers = Driver.objects.filter(company=company)
    return render(request, 'bus_admin/edit_bus.html', {
        'bus': bus,
        'routes': routes,
        'drivers': drivers,
    })


@bus_admin_required
def delete_bus(request, bus_id):
    """Delete a bus"""
    company = request.user.company
    bus = get_object_or_404(Bus, id=bus_id, company=company)
    bus.delete()
    messages.success(request, 'Bus deleted successfully.')
    return redirect('add_buses')
