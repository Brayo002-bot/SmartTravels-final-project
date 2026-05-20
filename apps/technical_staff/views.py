from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.gps.models import GPSPoint
from apps.systemadmin.models import Company
from .models import TechnicalStaff

User = get_user_model()


def company_admin_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if request.user.role not in ['bus_admin', 'train_admin', 'flight_admin']:
            raise PermissionDenied('Only company admins can manage technical staff.')

        if not request.user.company:
            raise PermissionDenied('No company is attached to this admin account.')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def technical_staff_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if request.user.role != 'technical_staff':
            raise PermissionDenied('Only technical staff may access this area.')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def _get_counts_for_company(company):
    bookings_today = 0
    pending_payments = 0
    parcels_today = 0
    transport_type = company.transport_type

    today = timezone.localdate()

    if transport_type == 'bus':
        from apps.buses.models import Booking

        bookings_today = Booking.objects.filter(bus__company=company, travel_date=today).count()
        pending_payments = Booking.objects.filter(bus__company=company, status='pending').count()
    elif transport_type == 'train':
        from apps.trains.models import Booking

        bookings_today = Booking.objects.filter(train__company=company, travel_date=today).count()
        pending_payments = Booking.objects.filter(train__company=company, status='pending').count()
    elif transport_type == 'flight':
        from apps.flights.models import Booking

        bookings_today = Booking.objects.filter(flight__company=company, travel_date=today).count()
        pending_payments = Booking.objects.filter(flight__company=company, status='pending').count()

    from apps.parcels.models import Parcel
    parcels_today = Parcel.objects.filter(created_at__date=today).count()

    return bookings_today, pending_payments, parcels_today


def _get_company_routes(company):
    transport_type = company.transport_type

    if transport_type == 'bus':
        from apps.buses.models import Route
        return Route.objects.filter(company=company)
    elif transport_type == 'train':
        from apps.trains.models import Route
        return Route.objects.filter(company=company)
    elif transport_type == 'flight':
        from apps.flights.models import Route
        return Route.objects.filter(company=company)

    return []


@technical_staff_required
def tech_dashboard(request):
    company = request.user.company
    bookings_today = 0
    pending_payments = 0
    parcels_today = 0
    company_routes = []
    transport_label = ''
    traffic_status = 'Monitoring traffic...'
    avg_speed = 0
    active_vehicles = 0

    if company:
        bookings_today, pending_payments, parcels_today = _get_counts_for_company(company)
        company_routes = _get_company_routes(company)
        transport_label = company.get_transport_type_display()

        vehicle_ids = []
        if company.transport_type == 'bus':
            from apps.buses.models import Bus
            vehicle_ids = list(Bus.objects.filter(company=company).values_list('id', flat=True))
        elif company.transport_type == 'train':
            from apps.trains.models import Train
            vehicle_ids = list(Train.objects.filter(company=company).values_list('id', flat=True))
        elif company.transport_type == 'flight':
            from apps.flights.models import Flight
            vehicle_ids = list(Flight.objects.filter(company=company).values_list('id', flat=True))

        if vehicle_ids:
            latest_points = GPSPoint.objects.filter(vehicle_type=company.transport_type, vehicle_id__in=vehicle_ids)
            avg_speed = latest_points.aggregate(avg_speed=Avg('speed_kmh'))['avg_speed'] or 0
            active_vehicles = latest_points.values('vehicle_id').distinct().count()
            if avg_speed < 25:
                traffic_status = 'Heavy congestion'
            elif avg_speed < 50:
                traffic_status = 'Moderate traffic'
            else:
                traffic_status = 'Clear roads'

    return render(request, 'technical_staff/tech_dashboard.html', {
        'company': company,
        'company_routes': company_routes,
        'transport_label': transport_label,
        'bookings_today': bookings_today,
        'pending_payments': pending_payments,
        'parcels_today': parcels_today,
        'traffic_status': traffic_status,
        'avg_speed': avg_speed,
        'active_vehicles': active_vehicles,
    })


@technical_staff_required
def tech_booking_assist(request):
    return render(request, 'technical_staff/tech_booking_assist.html')


@technical_staff_required
def tech_parcels(request):
    return render(request, 'technical_staff/tech_parcels.html')


@technical_staff_required
def tech_ticket_scanner(request):
    return render(request, 'technical_staff/tech_ticket_scanner.html')


@technical_staff_required
def tech_boarding(request):
    return render(request, 'technical_staff/tech_boarding.html')


@technical_staff_required
def tech_tracking(request):
    tracking_id = request.GET.get('tracking_id', '').strip()
    parcel = None
    parcel_logs = []
    from apps.parcels.models import Parcel

    if tracking_id:
        parcel = Parcel.objects.filter(parcel_id__iexact=tracking_id).first()
        if parcel:
            parcel_logs = parcel.logs.order_by('-timestamp')[:10]

    today = timezone.localdate()
    parcels_in_transit = Parcel.objects.filter(status='in_transit').count()
    delivered_today = Parcel.objects.filter(status='arrived', updated_at__date=today).count()
    pending_pickups = Parcel.objects.filter(status__in=['booked', 'dropped_off']).count()

    traffic_status = 'Monitoring traffic...'
    avg_speed = 0
    vehicle_ids = []
    company = request.user.company
    if company:
        if company.transport_type == 'bus':
            from apps.buses.models import Bus
            vehicle_ids = list(Bus.objects.filter(company=company).values_list('id', flat=True))
        elif company.transport_type == 'train':
            from apps.trains.models import Train
            vehicle_ids = list(Train.objects.filter(company=company).values_list('id', flat=True))
        elif company.transport_type == 'flight':
            from apps.flights.models import Flight
            vehicle_ids = list(Flight.objects.filter(company=company).values_list('id', flat=True))

    if vehicle_ids:
        latest_points = GPSPoint.objects.filter(vehicle_type=company.transport_type, vehicle_id__in=vehicle_ids)
        avg_speed = latest_points.aggregate(avg_speed=Avg('speed_kmh'))['avg_speed'] or 0
        if avg_speed < 25:
            traffic_status = 'Heavy congestion'
        elif avg_speed < 50:
            traffic_status = 'Moderate traffic'
        else:
            traffic_status = 'Clear roads'

    return render(request, 'technical_staff/tech_tracking.html', {
        'parcel': parcel,
        'parcel_logs': parcel_logs,
        'parcels_in_transit': parcels_in_transit,
        'delivered_today': delivered_today,
        'pending_pickups': pending_pickups,
        'traffic_status': traffic_status,
        'avg_speed': avg_speed,
    })


@company_admin_required
def manage_technical_staff(request):
    company = request.user.company
    staff_list = TechnicalStaff.objects.filter(company=company).order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_staff':
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            if not name:
                messages.error(request, 'Please enter a name for the technical staff.')
            else:
                TechnicalStaff.objects.create(name=name, phone=phone, company=company)
                messages.success(request, 'Technical staff added successfully.')
                return redirect('manage_technical_staff')

        elif action == 'assign_login':
            staff_id = request.POST.get('staff_id')
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '').strip()

            staff = get_object_or_404(TechnicalStaff, id=staff_id, company=company)
            if staff.user is not None:
                messages.warning(request, 'This technical staff member already has login credentials.')
                return redirect('manage_technical_staff')

            if not email or not password:
                messages.error(request, 'Please provide both email and password to assign login credentials.')
                return redirect('manage_technical_staff')

            if User.objects.filter(username=email).exists():
                messages.error(request, 'A user account with that email already exists.')
                return redirect('manage_technical_staff')

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                role='technical_staff',
            )
            user.company = company
            user.save()

            staff.user = user
            staff.save()
            messages.success(request, f'Login created for {staff.name}.')
            return redirect('manage_technical_staff')

    sidebar_template = 'bus_admin/sidebar.html'
    if request.user.role == 'train_admin':
        sidebar_template = 'train_admin/sidebar.html'
    elif request.user.role == 'flight_admin':
        sidebar_template = 'flight_admin/sidebar.html'

    return render(request, 'technical_staff/manage_staff.html', {
        'company': company,
        'staff_list': staff_list,
        'sidebar_template': sidebar_template,
    })
