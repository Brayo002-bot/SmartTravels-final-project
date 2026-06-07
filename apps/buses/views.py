from datetime import date
import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from apps.gps.models import GPSPoint
from apps.parcels.models import Parcel, ParcelLog
from apps.payments.models import Payment, MPesaService, find_passenger_user
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


def _generate_booking_reference():
    reference = uuid.uuid4().hex[:10].upper()
    if Booking.objects.filter(booking_reference=reference).exists():
        return _generate_booking_reference()
    return reference


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
        vip_price = request.POST.get('vip_price', 0)
        normal_price = request.POST.get('normal_price', 0)
        try:
            price = float(price) if price else 0
        except ValueError:
            price = 0
        try:
            vip_price = float(vip_price) if vip_price else 0
        except ValueError:
            vip_price = 0
        try:
            normal_price = float(normal_price) if normal_price else 0
        except ValueError:
            normal_price = 0
        if from_location and to_location:
            Route.objects.create(
                from_location=from_location,
                to_location=to_location,
                price=price,
                vip_price=vip_price,
                normal_price=normal_price,
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
        route.vip_price = float(request.POST.get('vip_price', 0) or 0)
        route.normal_price = float(request.POST.get('normal_price', 0) or 0)
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
        messages.warning(request, 'Passenger booking creation is disabled in admin dashboards. Manage existing bookings only.')
        return redirect('bus_booking')

    return render(request, 'bus_admin/booking.html', {
        'routes': routes,
        'buses': buses,
        'bookings': bookings,
        'allow_new_booking': False,
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

            # Extract first and last name from driver name
            name_parts = driver.name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role='driver',
                company=company
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
    cargo_items = Parcel.objects.filter(processed_by__company=company).order_by('-created_at')
    shipments_count = cargo_items.count()
    aggregates = cargo_items.aggregate(total_weight=Sum('weight_kg'), total_value=Sum('declared_value'))
    total_weight = float(aggregates['total_weight'] or 0)
    total_value = float(aggregates['total_value'] or 0)

    if request.method == 'POST':
        messages.warning(request, 'Parcel shipment creation is disabled in admin dashboards. Manage only parcels created by your technical staff.')
        return redirect('bus_cargo')
        recipient_name = request.POST.get('recipient_name', '').strip()
        recipient_email = request.POST.get('recipient_email', '').strip()
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
            passenger_account = find_passenger_user(sender_email, sender_phone)
            parcel_sender = passenger_account or request.user
            parcel = Parcel.objects.create(
                sender=parcel_sender,
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
                status='pending',
                notes=notes,
            )
            parcel.shipping_cost = parcel.calc_cost()
            parcel.save(update_fields=['shipping_cost'])
            payment_owner = passenger_account or request.user
            payment = Payment.objects.create(
                booking_reference=parcel.parcel_id,
                booking_type='parcel',
                passenger=payment_owner,
                amount=parcel.shipping_cost,
                method='mpesa',
                phone_number=sender_phone,
            )
            try:
                svc = MPesaService()
                res = svc.stk_push(sender_phone, parcel.shipping_cost, parcel.parcel_id)
                if res.get('ResponseCode') == '0':
                    payment.merchant_ref = res.get('CheckoutRequestID', '')
                    payment.save(update_fields=['merchant_ref'])
                    if settings.DEBUG:
                        payment.mark_completed(code='DEBUG-AUTO-' + parcel.parcel_id)
                        parcel.is_paid = True
                        parcel.status = 'booked'
                        parcel.save(update_fields=['is_paid','status'])
                        log_note = 'Cargo shipment created and auto-paid (DEBUG).'
                    else:
                        parcel.status = 'pending'
                        parcel.save(update_fields=['status'])
                        log_note = 'Cargo shipment created and awaiting payment via M-Pesa.'
                else:
                    payment.status = 'failed'
                    payment.save(update_fields=['status'])
                    log_note = 'Cargo shipment created but M-Pesa push failed.'
                    messages.warning(request, 'Cargo shipment created, but payment prompt failed. Please verify phone or MPesa settings.')
            except Exception as e:
                payment.status = 'failed'
                payment.save(update_fields=['status'])
                log_note = f'Cargo shipment created but payment prompt failed: {e}'
                messages.warning(request, f'Cargo shipment created, but payment prompt failed: {e}')

            ParcelLog.objects.create(
                parcel=parcel,
                status=parcel.status,
                location=origin,
                updated_by=request.user,
                note=log_note,
            )
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

            # send email notifications if emails are supplied
            try:
                from django.core.mail import send_mail
                from django.conf import settings as django_settings
                emails = []
                if sender_email:
                    emails.append(sender_email)
                if recipient_email:
                    emails.append(recipient_email)
                if emails:
                    send_mail(
                        f'SmartTravels Cargo Shipment Created - {parcel.parcel_id}',
                        f'Your cargo shipment {parcel.parcel_id} from {origin} to {destination} is now registered. Total cost is KES {parcel.shipping_cost:.2f}.',
                        django_settings.DEFAULT_FROM_EMAIL,
                        emails,
                        fail_silently=True,
                    )
            except Exception:
                pass

            if parcel.status == 'booked':
                messages.success(request, f'Cargo shipment {parcel.parcel_id} created and marked paid successfully.')
            else:
                messages.success(request, f'Cargo shipment {parcel.parcel_id} created successfully. Awaiting payment.')
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
        'page_description': 'Manage parcels created by your technical staff.',
        'transport_label': 'Bus',
        'category_choices': Parcel.CATEGORY,
        'vehicles': Bus.objects.filter(company=company, is_cargo=True),
        'allow_new_cargo': False,
    })



@bus_admin_required
def traffic(request):
    company = request.user.company
    bus_ids = list(Bus.objects.filter(company=company).values_list('id', flat=True))
    latest_points_qs = GPSPoint.objects.filter(vehicle_type='bus', vehicle_id__in=bus_ids)
    latest_points = latest_points_qs.select_related('driver').order_by('-recorded_at')[:20]
    avg_speed = latest_points.aggregate(avg_speed=Avg('speed_kmh'))['avg_speed'] or 0
    active_vehicles = latest_points_qs.values('vehicle_id').distinct().count()
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
