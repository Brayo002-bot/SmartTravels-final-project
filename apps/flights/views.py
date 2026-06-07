from datetime import date
import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Sum
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.gps.models import GPSPoint
from apps.parcels.models import Parcel, ParcelLog
from apps.payments.models import Payment, MPesaService, find_passenger_user
from apps.systemadmin.models import SeatLayoutHistory
from apps.systemadmin.seat_layout import generate_seat_layout, normalize_class_counts
from .models import Flight, Booking, Pilot, Route, Schedule

User = get_user_model()


def flight_admin_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.role != 'flight_admin' or not request.user.company or request.user.company.transport_type != 'flight':
            raise PermissionDenied('You do not have access to the flight admin section.')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def _generate_booking_reference():
    reference = uuid.uuid4().hex[:10].upper()
    if Booking.objects.filter(booking_reference=reference).exists():
        return _generate_booking_reference()
    return reference


@flight_admin_required
def flight_dashboard(request):
    company = request.user.company
    total_routes = Route.objects.filter(company=company).count()
    total_flights = Flight.objects.filter(company=company).count()
    todays_bookings = Booking.objects.filter(flight__company=company, travel_date=timezone.localdate()).count()
    todays_schedules = Schedule.objects.filter(flight__company=company, travel_date=timezone.localdate()).count()
    pending_reports = Booking.objects.filter(flight__company=company, status='pending').count()
    recent_bookings = Booking.objects.filter(flight__company=company).order_by('-created_at')[:5]

    return render(request, 'flight_admin/dashboard.html', {
        'total_routes': total_routes,
        'total_flights': total_flights,
        'todays_bookings': todays_bookings,
        'todays_schedules': todays_schedules,
        'pending_reports': pending_reports,
        'recent_bookings': recent_bookings,
    })


@flight_admin_required
def add_route(request):
    company = request.user.company
    if request.method == 'POST':
        from_location = request.POST.get('from_location', '').strip() or request.POST.get('from_city', '').strip()
        to_location = request.POST.get('to_location', '').strip() or request.POST.get('to_city', '').strip()
        price = request.POST.get('price', 0)
        try:
            price = float(price) if price else 0
        except ValueError:
            price = 0
        if from_location and to_location:
            first_class_price = float(request.POST.get('first_class_price', 0) or 0)
            business_price = float(request.POST.get('business_price', 0) or 0)
            economy_price = float(request.POST.get('economy_price', 0) or 0)
            Route.objects.create(
                from_location=from_location,
                to_location=to_location,
                price=price,
                first_class_price=first_class_price,
                business_price=business_price,
                economy_price=economy_price,
                company=company,
            )
            return redirect('flight_add_route')

    routes = Route.objects.filter(company=company).order_by('from_location', 'to_location')
    return render(request, 'flight_admin/add_route.html', {'routes': routes})


@flight_admin_required
def edit_route(request, route_id):
    company = request.user.company
    route = get_object_or_404(Route, id=route_id, company=company)
    if request.method == 'POST':
        route.from_location = request.POST.get('from_location', '').strip()
        route.to_location = request.POST.get('to_location', '').strip()
        route.price = float(request.POST.get('price', 0) or 0)
        route.first_class_price = float(request.POST.get('first_class_price', 0) or 0)
        route.business_price = float(request.POST.get('business_price', 0) or 0)
        route.economy_price = float(request.POST.get('economy_price', 0) or 0)
        route.save()
        messages.success(request, 'Route updated successfully.')
        return redirect('flight_add_route')
    return render(request, 'flight_admin/edit_route.html', {'route': route})


@flight_admin_required
def delete_route(request, route_id):
    company = request.user.company
    route = get_object_or_404(Route, id=route_id, company=company)
    route.delete()
    messages.success(request, 'Route deleted successfully.')
    return redirect('flight_add_route')


@flight_admin_required
def reports(request):
    company = request.user.company
    total_flights = Flight.objects.filter(company=company).count()
    total_pilots = Pilot.objects.filter(company=company).count()
    total_routes = Route.objects.filter(company=company).count()
    total_bookings = Booking.objects.filter(flight__company=company).count()
    bookings = Booking.objects.select_related('flight', 'route').filter(flight__company=company).order_by('-created_at')[:50]
    flights = Flight.objects.select_related('route', 'pilot').filter(company=company)

    return render(request, 'flight_admin/reports.html', {
        'total_flights': total_flights,
        'total_pilots': total_pilots,
        'total_routes': total_routes,
        'total_bookings': total_bookings,
        'bookings': bookings,
        'flights': flights,
    })


@flight_admin_required
def booking(request):
    company = request.user.company
    routes = Route.objects.filter(company=company)
    flights = Flight.objects.filter(company=company, available_seats__gt=0)
    bookings = Booking.objects.select_related('flight', 'route').filter(flight__company=company).order_by('-created_at')

    if request.method == 'POST':
        messages.warning(request, 'Passenger booking creation is disabled in admin dashboards. Manage existing bookings only.')
        return redirect('flight_booking')

    return render(request, 'flight_admin/booking.html', {
        'routes': routes,
        'flights': flights,
        'bookings': bookings,
        'allow_new_booking': False,
    })


@flight_admin_required
def get_available_seats(request):
    flight_id = request.GET.get('flight_id')
    travel_date = request.GET.get('travel_date')
    if not flight_id:
        return JsonResponse({'error': 'Flight ID required'}, status=400)

    company = request.user.company
    flight = get_object_or_404(Flight, id=flight_id, company=company)

    booked_qs = Booking.objects.filter(flight=flight)
    if travel_date:
        booked_qs = booked_qs.filter(travel_date=travel_date)
    booked_seats = list(booked_qs.exclude(seat_number__isnull=True).exclude(seat_number='').values_list('seat_number', flat=True))

    try:
        counts = {
            'first_class_seats': flight.first_class_seats,
            'business_seats': flight.business_seats,
            'economy_seats': flight.economy_seats,
        }
        layout = generate_seat_layout('flight', counts, booked_numbers=booked_seats, vehicle_id=flight.id)
        return JsonResponse(layout)
    except Exception:
        available = []
        for i in range(1, (flight.first_class_seats or 0) + (flight.business_seats or 0) + (flight.economy_seats or 0) + 1):
            seat_str = str(i)
            if seat_str not in booked_seats:
                available.append(seat_str)
        return JsonResponse({'available_seats': available})


@flight_admin_required
def schedule(request):
    company = request.user.company
    selected_date = request.GET.get('date')
    try:
        selected_date = date.fromisoformat(selected_date) if selected_date else timezone.localdate()
    except ValueError:
        selected_date = timezone.localdate()

    schedules = Schedule.objects.filter(travel_date=selected_date, flight__company=company).select_related('flight', 'flight__route').order_by('travel_time')
    flights = Flight.objects.filter(company=company)

    if request.method == 'POST':
        flight_id = request.POST.get('flight')
        travel_date = request.POST.get('travel_date')
        travel_time = request.POST.get('travel_time')

        if flight_id and travel_date and travel_time:
            flight = get_object_or_404(Flight, id=flight_id, company=company)
            Schedule.objects.create(
                flight=flight,
                travel_date=travel_date,
                travel_time=travel_time,
                price=flight.route.price,
            )
            return redirect('/flights/schedule/')

    return render(request, 'flight_admin/schedule.html', {
        'schedules': schedules,
        'flights': flights,
        'selected_date': selected_date,
    })


@flight_admin_required
def add_pilot(request):
    company = request.user.company
    if request.method == 'POST':
        if 'name' in request.POST:
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            if name and phone:
                Pilot.objects.create(name=name, phone=phone, company=company)
                messages.success(request, 'Pilot added successfully.')
                return redirect('add_pilot')

        if 'assign_login' in request.POST:
            pilot_id = request.POST.get('pilot_id')
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '').strip()

            pilot = get_object_or_404(Pilot, id=pilot_id, company=company)
            if pilot.user is not None:
                messages.warning(request, 'This pilot already has login credentials.')
                return redirect('add_pilot')

            if not email or not password:
                messages.error(request, 'Please provide both email and password to assign login credentials.')
                return redirect('add_pilot')

            if User.objects.filter(username=email).exists():
                messages.error(request, 'A user account with that email already exists.')
                return redirect('add_pilot')

            # Extract first and last name from pilot name
            name_parts = pilot.name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role='pilot',
                company=company
            )
            pilot.user = user
            pilot.save()

            messages.success(request, f'Login created for {pilot.name}.')
            return redirect('add_pilot')

    pilots = Pilot.objects.filter(company=company).order_by('name')
    return render(request, 'flight_admin/add_pilot.html', {'pilots': pilots})


@flight_admin_required
def add_flights(request):
    company = request.user.company
    if request.method == 'POST':
        flight_number = request.POST.get('flight_number', '').strip()
        description = request.POST.get('description', '').strip()
        route_id = request.POST.get('route')
        pilot_id = request.POST.get('pilot')
        vehicle_type = request.POST.get('vehicle_type', 'passenger')
        is_cargo = vehicle_type == 'cargo'
        total_passengers = int(request.POST.get('total_passengers') or 0)
        economy_seats = int(request.POST.get('economy_seats') or 0)
        business_seats = int(request.POST.get('business_seats') or 0)
        first_class_seats = int(request.POST.get('first_class_seats') or 0)

        if not is_cargo:
            if first_class_seats + business_seats + economy_seats <= 0 and total_passengers > 0:
                counts = normalize_class_counts('flight', total_passengers, {
                    'first_class_seats': 0.10,
                    'business_seats': 0.25,
                    'economy_seats': 0.65,
                })
                first_class_seats = counts['first_class_seats']
                business_seats = counts['business_seats']
                economy_seats = counts['economy_seats']
        else:
            first_class_seats = 0
            business_seats = 0
            economy_seats = 0

        if flight_number and route_id and pilot_id:
            route = get_object_or_404(Route, id=route_id, company=company)
            pilot = get_object_or_404(Pilot, id=pilot_id, company=company)
            flight = Flight.objects.create(
                flight_number=flight_number,
                description=description or None,
                is_cargo=is_cargo,
                route=route,
                pilot=pilot,
                company=company,
                economy_seats=economy_seats,
                business_seats=business_seats,
                first_class_seats=first_class_seats,
            )
            if not is_cargo:
                layout = generate_seat_layout(
                    'flight',
                    {
                        'first_class_seats': first_class_seats,
                        'business_seats': business_seats,
                        'economy_seats': economy_seats,
                    },
                    vehicle_id=flight.id,
                )
                SeatLayoutHistory.objects.create(
                    vehicle_type='flight',
                    vehicle_id=flight.id,
                    config={
                        'total_passengers': total_passengers,
                        'first_class_seats': first_class_seats,
                        'business_seats': business_seats,
                        'economy_seats': economy_seats,
                    },
                    layout=layout,
                )
            return redirect('add_flights')

    routes = Route.objects.filter(company=company)
    pilots = Pilot.objects.filter(company=company)
    flights = Flight.objects.select_related('route', 'pilot').filter(company=company)
    flight_ids = list(flights.values_list('id', flat=True))
    seat_layout_histories = SeatLayoutHistory.objects.filter(vehicle_type='flight', vehicle_id__in=flight_ids)[:10]
    return render(request, 'flight_admin/add_flights.html', {
        'routes': routes,
        'pilots': pilots,
        'flights': flights,
        'seat_layout_histories': seat_layout_histories,
    })


@flight_admin_required
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
        return redirect('flight_cargo')

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
                    v = Flight.objects.filter(id=vehicle_id, company=company).first()
                    if v:
                        parcel.assigned_vehicle_type = 'flight'
                        parcel.assigned_vehicle_id = v.id
                        parcel.assigned_vehicle_name = str(v)
                        parcel.save(update_fields=['assigned_vehicle_type','assigned_vehicle_id','assigned_vehicle_name'])
                except Exception:
                    pass

            try:
                from django.core.mail import send_mail
                from django.conf import settings as django_settings
                recipients = []
                if sender_email:
                    recipients.append(sender_email)
                if recipient_email:
                    recipients.append(recipient_email)
                if recipients:
                    send_mail(
                        f'SmartTravels Cargo Shipment Created - {parcel.parcel_id}',
                        f'Your cargo shipment {parcel.parcel_id} from {origin} to {destination} is now registered. Total cost is KES {parcel.shipping_cost:.2f}.',
                        django_settings.DEFAULT_FROM_EMAIL,
                        recipients,
                        fail_silently=True,
                    )
            except Exception:
                pass

            if parcel.status == 'booked':
                messages.success(request, f'Cargo shipment {parcel.parcel_id} created and marked paid successfully.')
            else:
                messages.success(request, f'Cargo shipment {parcel.parcel_id} created successfully. Awaiting payment.')
            return redirect('flight_cargo')
        else:
            messages.error(request, 'Please complete sender, recipient, origin and destination information.')

    return render(request, 'shared/admin_cargo.html', {
        'routes': routes,
        'cargo_items': cargo_items,
        'shipments_count': shipments_count,
        'total_weight': total_weight,
        'total_value': total_value,
        'sidebar_template': 'flight_admin/sidebar.html',
        'page_title': 'Flight Cargo Shipments',
        'page_description': 'Manage parcels created by your technical staff.',
        'transport_label': 'Flight',
        'category_choices': Parcel.CATEGORY,
        'vehicles': Flight.objects.filter(company=company, is_cargo=True),
        'allow_new_cargo': False,
    })


@flight_admin_required
def traffic(request):
    company = request.user.company
    flight_ids = list(Flight.objects.filter(company=company).values_list('id', flat=True))
    latest_points_qs = GPSPoint.objects.filter(vehicle_type='flight', vehicle_id__in=flight_ids)
    latest_points = latest_points_qs.select_related('driver').order_by('-recorded_at')[:20]
    avg_speed = latest_points.aggregate(avg_speed=Avg('speed_kmh'))['avg_speed'] or 0
    active_vehicles = latest_points_qs.values('vehicle_id').distinct().count()
    if avg_speed < 25:
        traffic_status = 'Heavy congestion'
    elif avg_speed < 50:
        traffic_status = 'Moderate traffic'
    else:
        traffic_status = 'Clear skies'

    return render(request, 'shared/admin_traffic.html', {
        'latest_gps': latest_points,
        'avg_speed': avg_speed,
        'active_vehicles': active_vehicles,
        'traffic_status': traffic_status,
        'sidebar_template': 'flight_admin/sidebar.html',
        'page_title': 'Flight Traffic Centre',
        'page_description': 'Monitor live flight GPS updates and route traffic conditions.',
        'transport_label': 'Flight',
    })


@flight_admin_required
def flight_seat_preview(request):
    total_passengers = int(request.GET.get('total_passengers') or 0)
    first_percent = float(request.GET.get('first_percent') or 0)
    business_percent = float(request.GET.get('business_percent') or 0)
    economy_percent = float(request.GET.get('economy_percent') or 0)
    first_class_seats = int(request.GET.get('first_class_seats') or 0)
    business_seats = int(request.GET.get('business_seats') or 0)
    economy_seats = int(request.GET.get('economy_seats') or 0)

    if total_passengers > 0:
        counts = normalize_class_counts('flight', total_passengers, {
            'first_class_seats': first_percent / 100,
            'business_seats': business_percent / 100,
            'economy_seats': economy_percent / 100,
        })
        first_class_seats = counts['first_class_seats']
        business_seats = counts['business_seats']
        economy_seats = counts['economy_seats']

    layout = generate_seat_layout(
        'flight',
        {
            'first_class_seats': first_class_seats,
            'business_seats': business_seats,
            'economy_seats': economy_seats,
        },
    )
    return JsonResponse(layout)


@flight_admin_required
def generate_flight_layout(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    company = request.user.company
    flight_id = request.POST.get('flight_id')
    total_passengers = int(request.POST.get('total_passengers') or 0)
    first_percent = float(request.POST.get('first_percent') or 0)
    business_percent = float(request.POST.get('business_percent') or 0)
    economy_percent = float(request.POST.get('economy_percent') or 0)
    first_class_seats = int(request.POST.get('first_class_seats') or 0)
    business_seats = int(request.POST.get('business_seats') or 0)
    economy_seats = int(request.POST.get('economy_seats') or 0)

    if total_passengers > 0:
        counts = normalize_class_counts('flight', total_passengers, {
            'first_class_seats': first_percent / 100,
            'business_seats': business_percent / 100,
            'economy_seats': economy_percent / 100,
        })
        first_class_seats = counts['first_class_seats']
        business_seats = counts['business_seats']
        economy_seats = counts['economy_seats']

    if not flight_id:
        return JsonResponse({'error': 'Missing flight_id'}, status=400)

    flight = get_object_or_404(Flight, id=flight_id, company=company)
    layout = generate_seat_layout(
        'flight',
        {
            'first_class_seats': first_class_seats,
            'business_seats': business_seats,
            'economy_seats': economy_seats,
        },
        vehicle_id=flight.id,
    )
    SeatLayoutHistory.objects.create(
        vehicle_type='flight',
        vehicle_id=flight.id,
        config={
            'total_passengers': total_passengers,
            'first_percent': first_percent,
            'business_percent': business_percent,
            'economy_percent': economy_percent,
            'first_class_seats': first_class_seats,
            'business_seats': business_seats,
            'economy_seats': economy_seats,
        },
        layout=layout,
    )

    return JsonResponse(layout)


@flight_admin_required
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
        return redirect('flight_company_profile')
    
    return render(request, 'flight_admin/company_profile.html', {'company': company})


@flight_admin_required
def edit_flight(request, flight_id):
    """Edit flight details"""
    company = request.user.company
    flight = get_object_or_404(Flight, id=flight_id, company=company)
    
    if request.method == 'POST':
        flight.flight_number = request.POST.get('flight_number', '').strip()
        flight.description = request.POST.get('description', '').strip() or None
        route_id = request.POST.get('route')
        pilot_id = request.POST.get('pilot')
        
        if route_id:
            flight.route = get_object_or_404(Route, id=route_id, company=company)
        if pilot_id:
            flight.pilot = get_object_or_404(Pilot, id=pilot_id, company=company)
        
        flight.save()
        messages.success(request, 'Flight updated successfully.')
        return redirect('add_flights')
    
    routes = Route.objects.filter(company=company)
    pilots = Pilot.objects.filter(company=company)
    return render(request, 'flight_admin/edit_flight.html', {
        'flight': flight,
        'routes': routes,
        'pilots': pilots,
    })


@flight_admin_required
def delete_flight(request, flight_id):
    """Delete a flight"""
    company = request.user.company
    flight = get_object_or_404(Flight, id=flight_id, company=company)
    flight.delete()
    messages.success(request, 'Flight deleted successfully.')
    return redirect('add_flights')
