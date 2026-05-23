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
    company = request.user.company
    routes = []
    available_trips = []

    query_from = request.POST.get('from_location', '').strip() if request.method == 'POST' else request.GET.get('from', '').strip()
    query_to = request.POST.get('destination', '').strip() if request.method == 'POST' else request.GET.get('to', '').strip()
    query_date = request.POST.get('travel_date', '').strip() if request.method == 'POST' else request.GET.get('date', '').strip()

    if company:
        routes = _get_company_routes(company)
        if request.method == 'POST' and query_from and query_to and query_date:
            if company.transport_type == 'bus':
                from apps.buses.models import Schedule
                schedules = Schedule.objects.filter(bus__company=company, travel_date=query_date, bus__is_cargo=False)
                for s in schedules:
                    if s.bus.route.from_location == query_from and s.bus.route.to_location == query_to:
                        available_trips.append({
                            'transport_type': 'Bus',
                            'available_seats': s.bus.available_seats,
                            'from_location': s.bus.route.from_location,
                            'to_location': s.bus.route.to_location,
                            'vehicle_name': str(s.bus),
                            'departure_time': s.travel_time,
                            'price': s.price,
                        })
            elif company.transport_type == 'train':
                from apps.trains.models import Schedule
                schedules = Schedule.objects.filter(train__company=company, travel_date=query_date, train__is_cargo=False)
                for s in schedules:
                    if s.train.route.from_location == query_from and s.train.route.to_location == query_to:
                        available_trips.append({
                            'transport_type': 'Train',
                            'available_seats': s.train.available_seats,
                            'from_location': s.train.route.from_location,
                            'to_location': s.train.route.to_location,
                            'vehicle_name': str(s.train),
                            'departure_time': s.travel_time,
                            'price': s.price,
                        })
            elif company.transport_type == 'flight':
                from apps.flights.models import Schedule
                schedules = Schedule.objects.filter(flight__company=company, travel_date=query_date, flight__is_cargo=False)
                for s in schedules:
                    if s.flight.route.from_location == query_from and s.flight.route.to_location == query_to:
                        available_trips.append({
                            'transport_type': 'Flight',
                            'available_seats': s.flight.available_seats,
                            'from_location': s.flight.route.from_location,
                            'to_location': s.flight.route.to_location,
                            'vehicle_name': str(s.flight),
                            'departure_time': s.travel_time,
                            'price': s.price,
                        })

    return render(request, 'technical_staff/tech_booking_assist.html', {
        'routes': routes,
        'available_trips': available_trips,
    })


@technical_staff_required
def tech_parcels(request):
    company = request.user.company
    routes = []
    buses = []
    trucks = []
    flights = []
    trains = []
    if company:
        if company.transport_type == 'bus':
            from apps.buses.models import Route as BusRoute, Bus
            routes = BusRoute.objects.filter(company=company)
            buses = Bus.objects.filter(company=company)
        elif company.transport_type == 'train':
            from apps.trains.models import Route as TrainRoute, Train
            routes = TrainRoute.objects.filter(company=company)
            trains = Train.objects.filter(company=company)
        elif company.transport_type == 'flight':
            from apps.flights.models import Route as FlightRoute, Flight
            routes = FlightRoute.objects.filter(company=company)
            flights = Flight.objects.filter(company=company)

    parcel_qr = None
    tracking_id = None

    if request.method == 'POST':
        from apps.parcels.models import Parcel, ParcelLog
        from apps.payments.models import Payment, MPesaService
        sender_name = request.POST.get('sender_name', '').strip() or str(request.user)
        sender_phone = request.POST.get('phone', '').strip() or request.user.phone_number or ''
        receiver_name = request.POST.get('receiver_name', '').strip()
        payment_phone = request.POST.get('payment_phone', '').strip() or sender_phone
        pickup_location = request.POST.get('pickup_location', '').strip() or ''
        destination = request.POST.get('destination', '').strip() or ''
        route_id = request.POST.get('route')
        parcel_type = request.POST.get('parcel_type', 'other')
        weight = float(request.POST.get('weight') or 1)
        amount = float(request.POST.get('amount') or 0)
        payment_status = request.POST.get('payment_status', 'Pending')
        description = request.POST.get('description', '').strip()

        if sender_name and sender_phone and receiver_name and pickup_location and destination:
            parcel = Parcel.objects.create(
                sender=request.user,
                sender_name=sender_name,
                sender_phone=sender_phone,
                recipient_name=receiver_name,
                recipient_phone=payment_phone,
                origin=pickup_location,
                destination=destination,
                category=parcel_type,
                description=description,
                weight_kg=weight,
                declared_value=0,
                shipping_cost=amount,
                is_fragile=False,
                is_paid=(payment_status == 'Paid'),
                status='booked' if payment_status == 'Paid' else 'booked',
            )
            ParcelLog.objects.create(parcel=parcel, status='booked', note='Registered by technical staff', updated_by=request.user)

            # assign vehicle if any
            transport_choice = request.POST.get('transport_choice')
            if transport_choice == 'bus' and request.POST.get('bus'):
                try:
                    from apps.buses.models import Bus
                    b = Bus.objects.filter(id=request.POST.get('bus'), company=company).first()
                    if b:
                        parcel.assigned_vehicle_type = 'bus'
                        parcel.assigned_vehicle_id = b.id
                        parcel.assigned_vehicle_name = str(b)
                except Exception:
                    pass
            elif transport_choice == 'truck' and request.POST.get('truck'):
                # trucks may be modelled differently; store id/name as provided
                parcel.assigned_vehicle_name = f"Truck {request.POST.get('truck')}"

            parcel.save()

            # If payment pending and amount provided, create Payment and push STK
            if payment_status == 'Pending' and amount > 0:
                try:
                    pay = Payment.objects.create(
                        booking_reference=parcel.parcel_id,
                        booking_type='parcel',
                        passenger=request.user,
                        amount=amount,
                        method='mpesa',
                        phone_number=payment_phone,
                    )
                    svc = MPesaService()
                    res = svc.stk_push(payment_phone, amount, parcel.parcel_id)
                    if isinstance(res, dict) and res.get('ResponseCode') == '0':
                        pay.merchant_ref = res.get('CheckoutRequestID', '')
                        pay.save(update_fields=['merchant_ref'])
                except Exception:
                    pass

            messages.success(request, 'Parcel registered. You can prompt payment if required.')
            return redirect('tech_parcels')

    return render(request, 'technical_staff/tech_parcels.html', {
        'routes': routes,
        'buses': buses,
        'trains': trains,
        'flights': flights,
        'parcel_qr': parcel_qr,
        'tracking_id': tracking_id,
    })


@technical_staff_required
def tech_ticket_scanner(request):
    return render(request, 'technical_staff/tech_ticket_scanner.html')


@technical_staff_required
def tech_boarding(request):
    company = request.user.company
    routes = _get_company_routes(company) if company else []
    buses = trains = flights = []
    selected_route = None
    selected_vehicle = None
    selected_date = request.GET.get('travel_date') or ''
    bookings = []

    # Load company vehicles
    if company:
        if company.transport_type == 'bus':
            from apps.buses.models import Route as BusRoute, Bus
            routes = BusRoute.objects.filter(company=company)
            buses = Bus.objects.filter(company=company)
        elif company.transport_type == 'train':
            from apps.trains.models import Route as TrainRoute, Train
            routes = TrainRoute.objects.filter(company=company)
            trains = Train.objects.filter(company=company)
        elif company.transport_type == 'flight':
            from apps.flights.models import Route as FlightRoute, Flight
            routes = FlightRoute.objects.filter(company=company)
            flights = Flight.objects.filter(company=company)

    # Handle POST actions: confirm boarding by booking_id or ticket
    if request.method == 'POST':
        booking_id = request.POST.get('booking_id')
        verify_ticket = request.POST.get('verify_ticket', '').strip()
        if booking_id:
            # mark booking as boarded
            from apps.buses.models import Booking as BusBooking
            from apps.trains.models import Booking as TrainBooking
            from apps.flights.models import Booking as FlightBooking
            for Model in (BusBooking, TrainBooking, FlightBooking):
                try:
                    b = Model.objects.filter(id=booking_id).first()
                    if b:
                        b.boarded = True
                        b.save(update_fields=['boarded'])
                        messages.success(request, 'Passenger marked as boarded.')
                        break
                except Exception:
                    continue
        elif verify_ticket:
            # try to find booking by booking reference
            from apps.buses.models import Booking as BusBooking
            from apps.trains.models import Booking as TrainBooking
            from apps.flights.models import Booking as FlightBooking
            for Model in (BusBooking, TrainBooking, FlightBooking):
                b = Model.objects.filter(booking_reference__iexact=verify_ticket).first()
                if b:
                    b.boarded = True
                    b.save(update_fields=['boarded'])
                    messages.success(request, 'Ticket validated and passenger boarded.')
                    break

        return redirect('tech_boarding')

    # GET: filter bookings based on selected vehicle and date
    selected_route_id = request.GET.get('route')
    selected_bus_id = request.GET.get('bus')
    selected_train_id = request.GET.get('train')
    selected_flight_id = request.GET.get('flight')

    if company and selected_date:
        if company.transport_type == 'bus' and selected_bus_id:
            from apps.buses.models import Bus, Booking as BusBooking
            selected_vehicle = Bus.objects.filter(id=selected_bus_id, company=company).first()
            if selected_vehicle:
                bookings = BusBooking.objects.filter(bus=selected_vehicle, travel_date=selected_date).order_by('seat_number')

        if company.transport_type == 'train' and selected_train_id:
            from apps.trains.models import Train, Booking as TrainBooking
            selected_vehicle = Train.objects.filter(id=selected_train_id, company=company).first()
            if selected_vehicle:
                bookings = TrainBooking.objects.filter(train=selected_vehicle, travel_date=selected_date).order_by('seat_number')

        if company.transport_type == 'flight' and selected_flight_id:
            from apps.flights.models import Flight, Booking as FlightBooking
            selected_vehicle = Flight.objects.filter(id=selected_flight_id, company=company).first()
            if selected_vehicle:
                bookings = FlightBooking.objects.filter(flight=selected_vehicle, travel_date=selected_date).order_by('seat_number')

    # Ensure bookings is a QuerySet so template methods like .count() work
    if not hasattr(bookings, 'count'):
        if company and company.transport_type == 'bus':
            from apps.buses.models import Booking as BusBooking
            bookings = BusBooking.objects.none()
        elif company and company.transport_type == 'train':
            from apps.trains.models import Booking as TrainBooking
            bookings = TrainBooking.objects.none()
        elif company and company.transport_type == 'flight':
            from apps.flights.models import Booking as FlightBooking
            bookings = FlightBooking.objects.none()

    return render(request, 'technical_staff/tech_boarding.html', {
        'company': company,
        'routes': routes,
        'buses': buses,
        'trains': trains,
        'flights': flights,
        'selected_bus': selected_vehicle if company and company.transport_type == 'bus' else None,
        'selected_train': selected_vehicle if company and company.transport_type == 'train' else None,
        'selected_flight': selected_vehicle if company and company.transport_type == 'flight' else None,
        'selected_route': int(selected_route_id) if selected_route_id else None,
        'selected_date': selected_date,
        'bookings': bookings,
    })


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
