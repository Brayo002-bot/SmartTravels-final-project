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
from .models import Train, Booking, Conductor, Route, Schedule

User = get_user_model()


def train_admin_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.role != 'train_admin' or not request.user.company or request.user.company.transport_type != 'train':
            raise PermissionDenied('You do not have access to the train admin section.')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def _generate_booking_reference():
    reference = uuid.uuid4().hex[:10].upper()
    if Booking.objects.filter(booking_reference=reference).exists():
        return _generate_booking_reference()
    return reference


@train_admin_required
def train_dashboard(request):
    company = request.user.company
    total_routes = Route.objects.filter(company=company).count()
    total_trains = Train.objects.filter(company=company).count()
    todays_bookings = Booking.objects.filter(train__company=company, travel_date=timezone.localdate()).count()
    todays_schedules = Schedule.objects.filter(train__company=company, travel_date=timezone.localdate()).count()
    pending_reports = Booking.objects.filter(train__company=company, status='pending').count()
    recent_bookings = Booking.objects.filter(train__company=company).order_by('-created_at')[:5]

    return render(request, 'train_admin/dashboard.html', {
        'total_routes': total_routes,
        'total_trains': total_trains,
        'todays_bookings': todays_bookings,
        'todays_schedules': todays_schedules,
        'pending_reports': pending_reports,
        'recent_bookings': recent_bookings,
    })


@train_admin_required
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

        if not from_location or not to_location:
            messages.error(request, 'Both from location and to location are required.')
        elif from_location == to_location:
            messages.error(request, 'From location and to location cannot be the same.')
        else:
            existing_route = Route.objects.filter(
                from_location__iexact=from_location,
                to_location__iexact=to_location,
                company=company
            ).exists()

            if existing_route:
                messages.warning(request, f'Route from {from_location} to {to_location} already exists.')
            else:
                vip_price = float(request.POST.get('vip_price', 0) or 0)
                business_price = float(request.POST.get('business_price', 0) or 0)
                economy_price = float(request.POST.get('economy_price', 0) or 0)
                parcel_base_price = float(request.POST.get('parcel_base_price', 0) or 0)
                other_destinations = [
                    stop.strip() for stop in request.POST.get('other_destinations', '').split(',') if stop.strip()
                ]
                Route.objects.create(
                    from_location=from_location,
                    to_location=to_location,
                    price=price,
                    first_class_price=vip_price,
                    business_price=business_price,
                    economy_price=economy_price,
                    parcel_base_price=parcel_base_price,
                    other_destinations=other_destinations,
                    company=company,
                )
                messages.success(request, f'Route from {from_location} to {to_location} added successfully.')
                return redirect('train_add_route')

    routes = Route.objects.filter(company=company).order_by('from_location', 'to_location')
    return render(request, 'train_admin/add_route.html', {'routes': routes})


@train_admin_required
def edit_route(request, route_id):
    company = request.user.company
    route = get_object_or_404(Route, id=route_id, company=company)
    if request.method == 'POST':
        route.from_location = request.POST.get('from_location', '').strip()
        route.to_location = request.POST.get('to_location', '').strip()
        route.price = float(request.POST.get('price', 0) or 0)
        route.first_class_price = float(request.POST.get('vip_price', 0) or 0)
        route.business_price = float(request.POST.get('business_price', 0) or 0)
        route.economy_price = float(request.POST.get('economy_price', 0) or 0)
        route.parcel_base_price = float(request.POST.get('parcel_base_price', 0) or 0)
        route.other_destinations = [
            stop.strip() for stop in request.POST.get('other_destinations', '').split(',') if stop.strip()
        ]
        route.save()
        messages.success(request, 'Route updated successfully.')
        return redirect('train_add_route')
    return render(request, 'train_admin/edit_route.html', {'route': route})


@train_admin_required
def delete_route(request, route_id):
    company = request.user.company
    route = get_object_or_404(Route, id=route_id, company=company)
    route.delete()
    messages.success(request, 'Route deleted successfully.')
    return redirect('train_add_route')


@train_admin_required
def reports(request):
    company = request.user.company
    total_trains = Train.objects.filter(company=company).count()
    total_conductors = Conductor.objects.filter(company=company).count()
    total_routes = Route.objects.filter(company=company).count()
    total_bookings = Booking.objects.filter(train__company=company).count()
    bookings = Booking.objects.select_related('train', 'route').filter(train__company=company).order_by('-created_at')[:50]
    trains = Train.objects.select_related('route', 'conductor').filter(company=company)

    return render(request, 'train_admin/reports.html', {
        'total_trains': total_trains,
        'total_conductors': total_conductors,
        'total_routes': total_routes,
        'total_bookings': total_bookings,
        'bookings': bookings,
        'trains': trains,
    })


@train_admin_required
def booking(request):
    company = request.user.company
    routes = Route.objects.filter(company=company)
    trains = Train.objects.filter(company=company, available_seats__gt=0)
    bookings = Booking.objects.select_related('train', 'route').filter(train__company=company).order_by('-created_at')

    if request.method == 'POST':
        messages.warning(request, 'Passenger booking creation is disabled in admin dashboards. Manage existing bookings only.')
        return redirect('train_booking')

    return render(request, 'train_admin/booking.html', {
        'routes': routes,
        'trains': trains,
        'bookings': bookings,
        'allow_new_booking': False,
    })


@train_admin_required
def get_available_seats(request):
    train_id = request.GET.get('train_id')
    travel_date = request.GET.get('travel_date')
    if not train_id:
        return JsonResponse({'error': 'Train ID required'}, status=400)

    company = request.user.company
    train = get_object_or_404(Train, id=train_id, company=company)

    booked_qs = Booking.objects.filter(train=train)
    if travel_date:
        booked_qs = booked_qs.filter(travel_date=travel_date)
    booked_seats = list(booked_qs.exclude(seat_number__isnull=True).exclude(seat_number='').values_list('seat_number', flat=True))

    try:
        counts = {
            'first_class_seats': train.first_class_seats,
            'business_seats': train.business_seats,
            'economy_seats': train.economy_seats,
        }
        layout = generate_seat_layout('train', counts, booked_numbers=booked_seats, vehicle_id=train.id)
        return JsonResponse(layout)
    except Exception:
        available = []
        for i in range(1, (train.first_class_seats or 0) + (train.business_seats or 0) + (train.economy_seats or 0) + 1):
            seat_str = str(i)
            if seat_str not in booked_seats:
                available.append(seat_str)
        return JsonResponse({'available_seats': available})


@train_admin_required
def schedule(request):
    company = request.user.company
    selected_date = request.GET.get('date')
    try:
        selected_date = date.fromisoformat(selected_date) if selected_date else timezone.localdate()
    except ValueError:
        selected_date = timezone.localdate()

    vehicle_type = request.GET.get('vehicle_type', 'all').lower()
    schedule_filters = {
        'travel_date': selected_date,
        'train__company': company,
    }
    if vehicle_type == 'cargo':
        schedule_filters['train__is_cargo'] = True
    elif vehicle_type == 'passenger':
        schedule_filters['train__is_cargo'] = False

    schedules = Schedule.objects.filter(**schedule_filters).select_related('train', 'train__route').order_by('travel_time')
    trains = Train.objects.filter(company=company)

    if request.method == 'POST':
        train_id = request.POST.get('train')
        travel_date = request.POST.get('travel_date')
        travel_time = request.POST.get('travel_time')

        if train_id and travel_date and travel_time:
            train = get_object_or_404(Train, id=train_id, company=company)
            Schedule.objects.create(
                train=train,
                travel_date=travel_date,
                travel_time=travel_time,
                price=train.route.price,
            )
            return redirect('/trains/schedule/')

    return render(request, 'train_admin/schedule.html', {
        'schedules': schedules,
        'trains': trains,
        'selected_date': selected_date,
    })


@train_admin_required
def add_conductor(request):
    company = request.user.company
    if request.method == 'POST':
        if 'name' in request.POST:
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            if name and phone:
                Conductor.objects.create(name=name, phone=phone, company=company)
                messages.success(request, 'Conductor added successfully.')
                return redirect('add_conductor')

        if 'assign_login' in request.POST:
            conductor_id = request.POST.get('conductor_id')
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '').strip()

            conductor = get_object_or_404(Conductor, id=conductor_id, company=company)
            if conductor.user is not None:
                messages.warning(request, 'This conductor already has login credentials.')
                return redirect('add_conductor')

            if not email or not password:
                messages.error(request, 'Please provide both email and password to assign login credentials.')
                return redirect('add_conductor')

            if User.objects.filter(username=email).exists():
                messages.error(request, 'A user account with that email already exists.')
                return redirect('add_conductor')

            # Extract first and last name from conductor name
            name_parts = conductor.name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role='conductor',
                company=company
            )
            conductor.user = user
            conductor.save()

            messages.success(request, f'Login created for {conductor.name}.')
            return redirect('add_conductor')

    conductors = Conductor.objects.filter(company=company).order_by('name')
    return render(request, 'train_admin/add_conductor.html', {'conductors': conductors})


@train_admin_required
def train_seat_preview(request):
    total_passengers = int(request.GET.get('total_passengers') or 0)
    first_percent = float(request.GET.get('first_percent') or 0)
    business_percent = float(request.GET.get('business_percent') or 0)
    economy_percent = float(request.GET.get('economy_percent') or 0)
    first_class_seats = int(request.GET.get('first_class_seats') or 0)
    business_seats = int(request.GET.get('business_seats') or 0)
    economy_seats = int(request.GET.get('economy_seats') or 0)

    if total_passengers > 0:
        counts = normalize_class_counts('train', total_passengers, {
            'first_class_seats': first_percent / 100,
            'business_seats': business_percent / 100,
            'economy_seats': economy_percent / 100,
        })
        first_class_seats = counts['first_class_seats']
        business_seats = counts['business_seats']
        economy_seats = counts['economy_seats']

    layout = generate_seat_layout(
        'train',
        {
            'first_class_seats': first_class_seats,
            'business_seats': business_seats,
            'economy_seats': economy_seats,
        },
    )
    return JsonResponse(layout)


@train_admin_required
def generate_train_layout(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    company = request.user.company
    train_id = request.POST.get('train_id')
    total_passengers = int(request.POST.get('total_passengers') or 0)
    first_percent = float(request.POST.get('first_percent') or 0)
    business_percent = float(request.POST.get('business_percent') or 0)
    economy_percent = float(request.POST.get('economy_percent') or 0)
    first_class_seats = int(request.POST.get('first_class_seats') or 0)
    business_seats = int(request.POST.get('business_seats') or 0)
    economy_seats = int(request.POST.get('economy_seats') or 0)

    if total_passengers > 0:
        counts = normalize_class_counts('train', total_passengers, {
            'first_class_seats': first_percent / 100,
            'business_seats': business_percent / 100,
            'economy_seats': economy_percent / 100,
        })
        first_class_seats = counts['first_class_seats']
        business_seats = counts['business_seats']
        economy_seats = counts['economy_seats']

    if not train_id:
        return JsonResponse({'error': 'Missing train_id'}, status=400)

    train = get_object_or_404(Train, id=train_id, company=company)
    layout = generate_seat_layout(
        'train',
        {
            'first_class_seats': first_class_seats,
            'business_seats': business_seats,
            'economy_seats': economy_seats,
        },
        vehicle_id=train.id,
    )
    SeatLayoutHistory.objects.create(
        vehicle_type='train',
        vehicle_id=train.id,
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


@train_admin_required
def add_trains(request):
    company = request.user.company
    if request.method == 'POST':
        train_number = request.POST.get('train_number', '').strip()
        description = request.POST.get('description', '').strip()
        route_id = request.POST.get('route')
        conductor_id = request.POST.get('conductor')
        vehicle_type = request.POST.get('vehicle_type', 'passenger')
        is_cargo = vehicle_type == 'cargo'
        total_passengers = int(request.POST.get('total_passengers') or 0)
        economy_seats = int(request.POST.get('economy_seats') or 0)
        business_seats = int(request.POST.get('business_seats') or 0)
        first_class_seats = int(request.POST.get('first_class_seats') or 0)

        if not is_cargo:
            if first_class_seats + business_seats + economy_seats <= 0 and total_passengers > 0:
                counts = normalize_class_counts('train', total_passengers, {
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

        if train_number and route_id and conductor_id:
            route = get_object_or_404(Route, id=route_id, company=company)
            conductor = get_object_or_404(Conductor, id=conductor_id, company=company)
            train = Train.objects.create(
                train_number=train_number,
                description=description or None,
                is_cargo=is_cargo,
                route=route,
                conductor=conductor,
                company=company,
                economy_seats=economy_seats,
                business_seats=business_seats,
                first_class_seats=first_class_seats,
            )
            if not is_cargo:
                layout = generate_seat_layout(
                    'train',
                    {
                        'first_class_seats': first_class_seats,
                        'business_seats': business_seats,
                        'economy_seats': economy_seats,
                    },
                    vehicle_id=train.id,
                )
                SeatLayoutHistory.objects.create(
                    vehicle_type='train',
                    vehicle_id=train.id,
                    config={
                        'total_passengers': total_passengers,
                        'first_class_seats': first_class_seats,
                        'business_seats': business_seats,
                        'economy_seats': economy_seats,
                    },
                    layout=layout,
                )
            return redirect('add_trains')

    routes = Route.objects.filter(company=company)
    conductors = Conductor.objects.filter(company=company)
    trains = Train.objects.select_related('route', 'conductor').filter(company=company)
    train_ids = list(trains.values_list('id', flat=True))
    seat_layout_histories = SeatLayoutHistory.objects.filter(vehicle_type='train', vehicle_id__in=train_ids)[:10]
    return render(request, 'train_admin/add_trains.html', {
        'routes': routes,
        'conductors': conductors,
        'trains': trains,
        'seat_layout_histories': seat_layout_histories,
    })


@train_admin_required
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
        return redirect('train_cargo')

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
                    v = Train.objects.filter(id=vehicle_id, company=company).first()
                    if v:
                        parcel.assigned_vehicle_type = 'train'
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
            return redirect('train_cargo')
        else:
            messages.error(request, 'Please complete sender, recipient, origin and destination information.')

    return render(request, 'shared/admin_cargo.html', {
        'routes': routes,
        'cargo_items': cargo_items,
        'shipments_count': shipments_count,
        'total_weight': total_weight,
        'total_value': total_value,
        'sidebar_template': 'train_admin/sidebar.html',
        'page_title': 'Train Cargo Shipments',
        'page_description': 'Manage parcels created by your technical staff.',
        'transport_label': 'Train',
        'category_choices': Parcel.CATEGORY,
        'vehicles': Train.objects.filter(company=company, is_cargo=True),
        'allow_new_cargo': False,
    })


@train_admin_required
def traffic(request):
    company = request.user.company
    train_ids = list(Train.objects.filter(company=company).values_list('id', flat=True))
    latest_points_qs = GPSPoint.objects.filter(vehicle_type='train', vehicle_id__in=train_ids)
    latest_points = latest_points_qs.select_related('driver').order_by('-recorded_at')[:20]
    avg_speed = latest_points.aggregate(avg_speed=Avg('speed_kmh'))['avg_speed'] or 0
    active_vehicles = latest_points_qs.values('vehicle_id').distinct().count()
    if avg_speed < 25:
        traffic_status = 'Heavy congestion'
    elif avg_speed < 50:
        traffic_status = 'Moderate traffic'
    else:
        traffic_status = 'Clear rails'

    return render(request, 'shared/admin_traffic.html', {
        'latest_gps': latest_points,
        'avg_speed': avg_speed,
        'active_vehicles': active_vehicles,
        'traffic_status': traffic_status,
        'sidebar_template': 'train_admin/sidebar.html',
        'page_title': 'Train Traffic Centre',
        'page_description': 'Monitor live train GPS updates and route traffic conditions.',
        'transport_label': 'Train',
    })


@train_admin_required
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
        return redirect('train_company_profile')
    
    return render(request, 'train_admin/company_profile.html', {'company': company})


@train_admin_required
def edit_train(request, train_id):
    """Edit train details"""
    company = request.user.company
    train = get_object_or_404(Train, id=train_id, company=company)
    
    if request.method == 'POST':
        train.train_number = request.POST.get('train_number', '').strip()
        train.description = request.POST.get('description', '').strip() or None
        route_id = request.POST.get('route')
        conductor_id = request.POST.get('conductor')
        
        if route_id:
            train.route = get_object_or_404(Route, id=route_id, company=company)
        if conductor_id:
            train.conductor = get_object_or_404(Conductor, id=conductor_id, company=company)
        
        train.save()
        messages.success(request, 'Train updated successfully.')
        return redirect('add_trains')
    
    routes = Route.objects.filter(company=company)
    conductors = Conductor.objects.filter(company=company)
    return render(request, 'train_admin/edit_train.html', {
        'train': train,
        'routes': routes,
        'conductors': conductors,
    })


@train_admin_required
def delete_train(request, train_id):
    """Delete a train"""
    company = request.user.company
    train = get_object_or_404(Train, id=train_id, company=company)
    train.delete()
    messages.success(request, 'Train deleted successfully.')
    return redirect('add_trains')
    
    return render(request, 'train_admin/company_profile.html', {'company': company})
