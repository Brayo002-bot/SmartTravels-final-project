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
                Route.objects.create(from_location=from_location, to_location=to_location, price=price, company=company)
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
        passenger_name = request.POST.get('passenger_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        route_id = request.POST.get('route')
        train_id = request.POST.get('train')
        travel_date = request.POST.get('travel_date')

        if passenger_name and phone and route_id and train_id and travel_date:
            train = get_object_or_404(Train, id=train_id, company=company)
            route = get_object_or_404(Route, id=route_id, company=company)

            if train.available_seats > 0:
                Booking.objects.create(
                    passenger_name=passenger_name,
                    phone=phone,
                    train=train,
                    route=route,
                    travel_date=travel_date,
                    status='confirmed',
                )
                train.available_seats -= 1
                train.save()
                return redirect('train_booking')

    return render(request, 'train_admin/booking.html', {
        'routes': routes,
        'trains': trains,
        'bookings': bookings,
    })


@train_admin_required
def schedule(request):
    company = request.user.company
    selected_date = request.GET.get('date')
    try:
        selected_date = date.fromisoformat(selected_date) if selected_date else timezone.localdate()
    except ValueError:
        selected_date = timezone.localdate()

    schedules = Schedule.objects.filter(travel_date=selected_date, train__company=company).select_related('train', 'train__route').order_by('travel_time')
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

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                role='conductor'
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
        total_passengers = int(request.POST.get('total_passengers') or 0)
        first_percent = float(request.POST.get('first_percent') or 0)
        business_percent = float(request.POST.get('business_percent') or 0)
        economy_percent = float(request.POST.get('economy_percent') or 0)
        economy_seats = int(request.POST.get('economy_seats') or 0)
        business_seats = int(request.POST.get('business_seats') or 0)
        first_class_seats = int(request.POST.get('first_class_seats') or 0)

        if total_passengers > 0:
            counts = normalize_class_counts('train', total_passengers, {
                'first_class_seats': first_percent / 100,
                'business_seats': business_percent / 100,
                'economy_seats': economy_percent / 100,
            })
            first_class_seats = counts['first_class_seats']
            business_seats = counts['business_seats']
            economy_seats = counts['economy_seats']

        if train_number and route_id and conductor_id:
            route = get_object_or_404(Route, id=route_id, company=company)
            conductor = get_object_or_404(Conductor, id=conductor_id, company=company)
            train = Train.objects.create(
                train_number=train_number,
                description=description or None,
                route=route,
                conductor=conductor,
                company=company,
                economy_seats=economy_seats,
                business_seats=business_seats,
                first_class_seats=first_class_seats,
            )
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
        'page_description': 'Create cargo and parcel shipments for your train routes.',
        'transport_label': 'Train',
        'category_choices': Parcel.CATEGORY,
    })


@train_admin_required
def traffic(request):
    company = request.user.company
    train_ids = list(Train.objects.filter(company=company).values_list('id', flat=True))
    latest_points = GPSPoint.objects.filter(vehicle_type='train', vehicle_id__in=train_ids).select_related('driver').order_by('-recorded_at')[:20]
    avg_speed = latest_points.aggregate(avg_speed=Avg('speed_kmh'))['avg_speed'] or 0
    active_vehicles = latest_points.values('vehicle_id').distinct().count()
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
