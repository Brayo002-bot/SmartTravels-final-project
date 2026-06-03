from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.gps.models import GPSPoint
from apps.payments.models import MPesaService, find_passenger_user
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
    from django.core.mail import send_mail
    from django.conf import settings as django_settings
    from apps.payments.models import Payment, MPesaService
    import uuid
    import logging
    
    logger = logging.getLogger(__name__)
    company = request.user.company
    routes = []
    available_trips = []
    bookings = None

    query_from = request.POST.get('from_location', '').strip() if request.method == 'POST' else request.GET.get('from', '').strip()
    query_to = request.POST.get('destination', '').strip() if request.method == 'POST' else request.GET.get('to', '').strip()
    query_date = request.POST.get('travel_date', '').strip() if request.method == 'POST' else request.GET.get('date', '').strip()

    # Handle booking passenger with one-click payment prompt
    if request.method == 'POST' and 'book_passenger' in request.POST:
        passenger_name = request.POST.get('passenger_name', '').strip()
        passenger_phone = request.POST.get('phone', '').strip()
        passenger_email = request.POST.get('passenger_email', '').strip()
        schedule_id = request.POST.get('book_passenger', '').strip()
        selected_seat = request.POST.get('selected_seat', '').strip()
        selected_seat_class = request.POST.get('selected_seat_class', '').strip()
        travel_date = request.POST.get('travel_date', '').strip()
        from_loc = request.POST.get('from_location', '').strip()
        to_loc = request.POST.get('destination', '').strip()

        logger.info(f'📝 Booking attempt - Name: {passenger_name}, Phone: {passenger_phone}, Email: {passenger_email}, ScheduleID: {schedule_id}, Seat: {selected_seat}')

        if not all([passenger_name, passenger_phone, passenger_email, schedule_id, travel_date, from_loc, to_loc]):
            logger.warning(f'❌ Missing booking details: name={bool(passenger_name)}, phone={bool(passenger_phone)}, email={bool(passenger_email)}, schedule_id={bool(schedule_id)}, date={bool(travel_date)}, from={bool(from_loc)}, to={bool(to_loc)}')
            messages.error(request, '❌ Please fill in all passenger and trip details before booking.')
        elif not selected_seat:
            messages.error(request, 'Please select a seat before sending the payment prompt.')
        else:
            try:
                # Find the vehicle and its schedule
                vehicle = None
                schedule = None
                booking_conflict = False
                booking_reference = f'TECH{uuid.uuid4().hex[:8].upper()}'
                price = 0
                departure_time = ''

                if company.transport_type == 'bus':
                    from apps.buses.models import Bus, Booking, Schedule
                    schedule = Schedule.objects.filter(
                        pk=schedule_id,
                        bus__company=company,
                        travel_date=travel_date,
                        bus__route__from_location=from_loc,
                        bus__route__to_location=to_loc,
                        bus__is_cargo=False,
                    ).first()
                    if schedule:
                        vehicle = schedule.bus
                        price = schedule.price
                        departure_time = schedule.travel_time or ''
                        if Booking.objects.filter(bus=vehicle, travel_date=travel_date, seat_number=selected_seat).exists():
                            messages.error(request, f'Seat {selected_seat} is already booked for this trip. Choose another seat.')
                            booking_conflict = True
                            schedule = None
                            vehicle = None
                        else:
                            # Determine price based on seat class
                            price = schedule.price
                            if selected_seat_class == 'VIP' and vehicle.route.vip_price:
                                price = vehicle.route.vip_price
                            elif selected_seat_class == 'Normal' and vehicle.route.normal_price:
                                price = vehicle.route.normal_price
                            
                            booking = Booking.objects.create(
                                booking_reference=booking_reference,
                                passenger_name=passenger_name,
                                phone=passenger_phone,
                                bus=vehicle,
                                route=vehicle.route,
                                travel_date=travel_date,
                                travel_time=departure_time,
                                seat_number=selected_seat,
                                price=price,
                                status='pending',
                            )

                elif company.transport_type == 'train':
                    from apps.trains.models import Train, Booking, Schedule
                    schedule = Schedule.objects.filter(
                        pk=schedule_id,
                        train__company=company,
                        travel_date=travel_date,
                        train__route__from_location=from_loc,
                        train__route__to_location=to_loc,
                        train__is_cargo=False,
                    ).first()
                    if schedule:
                        vehicle = schedule.train
                        price = schedule.price
                        departure_time = schedule.travel_time or ''
                        if Booking.objects.filter(train=vehicle, travel_date=travel_date, seat_number=selected_seat).exists():
                            messages.error(request, f'Seat {selected_seat} is already booked for this trip. Choose another seat.')
                            booking_conflict = True
                            schedule = None
                            vehicle = None
                        else:
                            # Determine price based on seat class
                            price = schedule.price
                            if selected_seat_class == 'First Class' and vehicle.route.first_class_price:
                                price = vehicle.route.first_class_price
                            elif selected_seat_class == 'Business' and vehicle.route.business_price:
                                price = vehicle.route.business_price
                            elif selected_seat_class == 'Economy' and vehicle.route.economy_price:
                                price = vehicle.route.economy_price
                            
                            booking = Booking.objects.create(
                                booking_reference=booking_reference,
                                passenger_name=passenger_name,
                                phone=passenger_phone,
                                train=vehicle,
                                route=vehicle.route,
                                travel_date=travel_date,
                                travel_time=departure_time,
                                seat_number=selected_seat,
                                price=price,
                                status='pending',
                            )

                elif company.transport_type == 'flight':
                    from apps.flights.models import Flight, Booking, Schedule
                    schedule = Schedule.objects.filter(
                        pk=schedule_id,
                        flight__company=company,
                        travel_date=travel_date,
                        flight__route__from_location=from_loc,
                        flight__route__to_location=to_loc,
                        flight__is_cargo=False,
                    ).first()
                    if schedule:
                        vehicle = schedule.flight
                        price = schedule.price
                        departure_time = schedule.travel_time or ''
                        if Booking.objects.filter(flight=vehicle, travel_date=travel_date, seat_number=selected_seat).exists():
                            messages.error(request, f'Seat {selected_seat} is already booked for this trip. Choose another seat.')
                            booking_conflict = True
                            schedule = None
                            vehicle = None
                        else:
                            # Determine price based on seat class
                            price = schedule.price
                            if selected_seat_class == 'First Class' and vehicle.route.first_class_price:
                                price = vehicle.route.first_class_price
                            elif selected_seat_class == 'Business' and vehicle.route.business_price:
                                price = vehicle.route.business_price
                            elif selected_seat_class == 'Economy' and vehicle.route.economy_price:
                                price = vehicle.route.economy_price
                            
                            booking = Booking.objects.create(
                                booking_reference=booking_reference,
                                passenger_name=passenger_name,
                                phone=passenger_phone,
                                flight=vehicle,
                                route=vehicle.route,
                                travel_date=travel_date,
                                travel_time=departure_time,
                                seat_number=selected_seat,
                                price=price,
                                status='pending',
                            )

                if schedule and vehicle:
                    # Prefer the passenger account if they exist for loyalty and dashboards
                    passenger_account = find_passenger_user(passenger_email, passenger_phone)
                    payment_owner = passenger_account or request.user

                    payment = Payment.objects.create(
                        booking_reference=booking_reference,
                        booking_type=company.transport_type,
                        passenger=payment_owner,
                        amount=price,
                        method='mpesa',
                        phone_number=passenger_phone,
                    )

                    try:
                        # Send M-Pesa STK push
                        svc = MPesaService()
                        res = svc.stk_push(passenger_phone, price, booking_reference)
                        logger.info(f'📊 STK Push Response: ResponseCode={res.get("ResponseCode")} | {res}')

                        if res.get('ResponseCode') == '0':
                            payment.merchant_ref = res.get('CheckoutRequestID', '')
                            payment.save(update_fields=['merchant_ref'])

                            # In debug mode, auto-complete payment
                            if django_settings.DEBUG:
                                payment.mark_completed(code='DEBUG-AUTO-' + booking_reference)
                                booking.status = 'confirmed'
                                booking.save(update_fields=['status'])
                                logger.info(f'✅ Auto-completed payment for {booking_reference}')

                                # Send ticket PDF email for technical staff assisted bookings
                                try:
                                    from apps.accounts.views import _send_ticket_email
                                    if _send_ticket_email(passenger_email, booking):
                                        logger.info(f'📧 Ticket PDF emailed to {passenger_email}')
                                    else:
                                        logger.warning(f'Unable to email ticket PDF to {passenger_email}')
                                except Exception as e:
                                    logger.warning(f'Email send failed: {e}')

                                messages.success(
                                    request,
                                    f'✅ Booking confirmed! Ticket PDF emailed to {passenger_email} | M-Pesa payment auto-completed (DEBUG MODE)'
                                )
                            else:
                                # Production: wait for callback
                                messages.success(
                                    request,
                                    f'📱 M-Pesa payment prompt sent to {passenger_phone}. Ticket will be sent after payment confirmation.'
                                )
                    except Exception as e:
                        logger.exception(f'M-Pesa error: {str(e)}')
                        messages.warning(request, f'Booking created but M-Pesa prompt failed: {str(e)}')
                elif not booking_conflict:
                    logger.warning(f'Trip not found: schedule_id={schedule_id}, from={from_loc}, to={to_loc}, date={travel_date}')
                    messages.error(request, 'Could not find the selected trip. Please search again.')
            except Exception as e:
                logger.exception(f'Booking error: {str(e)}')
                messages.error(request, f'Booking failed: {str(e)}')

    if company:
        routes = _get_company_routes(company)
        if company.transport_type == 'bus':
            from apps.buses.models import Booking as BusBooking
            bookings = BusBooking.objects.filter(bus__company=company).order_by('-created_at')[:5]
        elif company.transport_type == 'train':
            from apps.trains.models import Booking as TrainBooking
            bookings = TrainBooking.objects.filter(train__company=company).order_by('-created_at')[:5]
        elif company.transport_type == 'flight':
            from apps.flights.models import Booking as FlightBooking
            bookings = FlightBooking.objects.filter(flight__company=company).order_by('-created_at')[:5]

        if request.method == 'POST' and 'search_trip' in request.POST and query_from and query_to and query_date:
            if company.transport_type == 'bus':
                from apps.buses.models import Schedule
                schedules = Schedule.objects.filter(bus__company=company, travel_date=query_date, bus__is_cargo=False)
                for s in schedules:
                    if s.bus.route.from_location == query_from and s.bus.route.to_location == query_to:
                        available_trips.append({
                            'transport_type': 'Bus',
                            'mode': 'bus',
                            'company': s.bus.company.name,
                            'available_seats': s.bus.available_seats,
                            'from_location': s.bus.route.from_location,
                            'to_location': s.bus.route.to_location,
                            'vehicle_name': str(s.bus),
                            'departure_time': s.travel_time,
                            'price': s.price,
                            'schedule_id': s.id,
                        })
            elif company.transport_type == 'train':
                from apps.trains.models import Schedule
                schedules = Schedule.objects.filter(train__company=company, travel_date=query_date, train__is_cargo=False)
                for s in schedules:
                    if s.train.route.from_location == query_from and s.train.route.to_location == query_to:
                        available_trips.append({
                            'transport_type': 'Train',
                            'mode': 'train',
                            'company': s.train.company.name,
                            'available_seats': s.train.available_seats,
                            'from_location': s.train.route.from_location,
                            'to_location': s.train.route.to_location,
                            'vehicle_name': str(s.train),
                            'departure_time': s.travel_time,
                            'price': s.price,
                            'schedule_id': s.id,
                        })
            elif company.transport_type == 'flight':
                from apps.flights.models import Schedule
                schedules = Schedule.objects.filter(flight__company=company, travel_date=query_date, flight__is_cargo=False)
                for s in schedules:
                    if s.flight.route.from_location == query_from and s.flight.route.to_location == query_to:
                        available_trips.append({
                            'transport_type': 'Flight',
                            'mode': 'flight',
                            'company': s.flight.company.name,
                            'available_seats': s.flight.available_seats,
                            'from_location': s.flight.route.from_location,
                            'to_location': s.flight.route.to_location,
                            'vehicle_name': str(s.flight),
                            'departure_time': s.travel_time,
                            'price': s.price,
                            'schedule_id': s.id,
                        })

    if bookings is None:
        bookings = []

    return render(request, 'technical_staff/tech_booking_assist.html', {
        'routes': routes,
        'available_trips': available_trips,
        'bookings': bookings,
    })


@technical_staff_required
def tech_parcels(request):
    company = request.user.company
    routes = []
    buses = []
    flights = []
    trains = []
    available_vehicles = []
    stations = []
    company_name = company.name if company else ''

    if company:
        if company.transport_type == 'bus':
            from apps.buses.models import Route as BusRoute, Bus
            routes = BusRoute.objects.filter(company=company)
            buses = Bus.objects.filter(company=company)
            available_vehicles = [
                {
                    'value': f'bus:{bus.id}',
                    'label': f'🚌 {bus.bus_number} — {bus.route.from_location} → {bus.route.to_location}',
                }
                for bus in buses
            ]
        elif company.transport_type == 'train':
            from apps.trains.models import Route as TrainRoute, Train
            routes = TrainRoute.objects.filter(company=company)
            trains = Train.objects.filter(company=company)
            available_vehicles = [
                {
                    'value': f'train:{train.id}',
                    'label': f'🚆 {train.train_number} — {train.route.from_location} → {train.route.to_location}',
                }
                for train in trains
            ]
        elif company.transport_type == 'flight':
            from apps.flights.models import Route as FlightRoute, Flight
            routes = FlightRoute.objects.filter(company=company)
            flights = Flight.objects.filter(company=company)
            available_vehicles = [
                {
                    'value': f'flight:{flight.id}',
                    'label': f'✈️ {flight.flight_number} — {flight.route.from_location} → {flight.route.to_location}',
                }
                for flight in flights
            ]

        station_set = set()
        for route in routes:
            station_set.add(route.from_location)
            station_set.add(route.to_location)
        stations = sorted(station_set)

    parcel_qr = None
    tracking_id = None
    prompt_sent = request.session.get('tech_parcels_prompt_sent', False)
    stk_sent = request.session.get('tech_parcels_stk_sent', False)
    stk_phone = request.session.get('tech_parcels_stk_phone', '')

    default_context = {
        'company_name': company_name,
        'routes': routes,
        'stations': stations,
        'available_vehicles': available_vehicles,
        'buses': buses,
        'trains': trains,
        'flights': flights,
        'parcel_qr': parcel_qr,
        'tracking_id': tracking_id,
        'prompt_sent': prompt_sent,
        'stk_sent': stk_sent,
        'stk_phone': stk_phone,
    }

    if request.method == 'POST':
        from apps.parcels.models import Parcel, ParcelLog
        from apps.payments.models import Payment, MPesaService
        import base64
        import io
        import qrcode

        prompt_action = request.POST.get('prompt_action', 'send_prompt')
        sender_name = request.POST.get('sender_name', '').strip() or str(request.user)
        sender_phone = request.POST.get('phone', '').strip() or request.user.phone_number or ''
        sender_email = request.POST.get('sender_email', '').strip() or getattr(request.user, 'email', '')
        sender_id = request.POST.get('sender_id', '').strip()
        sender_phone = request.POST.get('sender_phone', '').strip()
        receiver_name = request.POST.get('receiver_name', '').strip()
        receiver_phone = request.POST.get('receiver_phone', '').strip()
        recipient_email = request.POST.get('receiver_email', '').strip()
        payment_phone = request.POST.get('mpesa_phone', '').strip() or sender_phone
        pickup_location = request.POST.get('pickup_location', '').strip() or ''
        pickup_office = request.POST.get('pickup_office', '').strip() or ''
        destination = request.POST.get('destination', '').strip() or ''
        route_id = request.POST.get('route')
        parcel_type = request.POST.get('parcel_type', 'other').strip().lower()
        weight = float(request.POST.get('weight') or 1)
        declared_value = float(request.POST.get('declared_value') or 0)
        amount = float(request.POST.get('amount') or 0)
        payment_status = request.POST.get('payment_status', 'Pending')
        description = request.POST.get('description', '').strip()
        item_image = request.FILES.get('item_image')

        form_data = {
            'sender_name': sender_name,
            'sender_id': sender_id,
            'sender_phone': sender_phone,
            'sender_email': sender_email,
            'receiver_name': receiver_name,
            'receiver_phone': receiver_phone,
            'recipient_email': recipient_email,
            'mpesa_phone': payment_phone,
            'pickup_location': pickup_location,
            'pickup_office': pickup_office,
            'destination': destination,
            'route': route_id,
            'parcel_type': parcel_type,
            'weight': weight,
            'declared_value': declared_value,
            'amount': amount,
            'payment_status': payment_status,
            'description': description,
        }

        if prompt_action == 'send_prompt':
            if not all([sender_name, sender_phone, sender_email, receiver_name, receiver_phone, recipient_email, pickup_location, pickup_office, destination]):
                messages.error(request, 'Complete all sender/receiver contact, route, origin station, pickup office, and email details before sending the confirmation prompt.')
                return render(request, 'technical_staff/tech_parcels.html', {
                    'routes': routes,
                    'buses': buses,
                    'trains': trains,
                    'flights': flights,
                    'prompt_sent': prompt_sent,
                    'stk_sent': stk_sent,
                    'form_data': form_data,
                })

            recipients = []
            if sender_email:
                recipients.append(sender_email)
            if recipient_email and recipient_email != sender_email:
                recipients.append(recipient_email)

            if recipients:
                prompt_subject = f"SmartTravels Parcel Confirmation Request"
                prompt_body = (
                    f"Dear customer,\n\n"
                    f"A parcel confirmation request has been initiated for sender {sender_name} and receiver {receiver_name}.\n"
                    f"Route: {pickup_location} → {destination}\n"
                    f"Pickup office: {pickup_office}\n"
                    f"Estimated item value: KES {declared_value:.2f}\n"
                    f"Please allow the technical staff to proceed with payment collection.\n\n"
                    f"Thank you,\nSmartTravels Logistics Team"
                )
                try:
                    send_mail(prompt_subject, prompt_body, getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@smarttravels.local'), recipients, fail_silently=False)
                    request.session['tech_parcels_prompt_sent'] = True
                    prompt_sent = True
                    messages.success(request, 'Confirmation prompt sent to sender and receiver. Proceed to payment collection.')
                except Exception as exc:
                    messages.error(request, f'Failed to send confirmation prompt: {exc}')

            return render(request, 'technical_staff/tech_parcels.html', {
                **default_context,
                'prompt_sent': prompt_sent,
                'stk_sent': stk_sent,
                'form_data': form_data,
                'active_step': 2,
            })

        if prompt_action == 'send_stk':
            if not request.session.get('tech_parcels_prompt_sent'):
                recipients = []
                if sender_email:
                    recipients.append(sender_email)
                if recipient_email and recipient_email != sender_email:
                    recipients.append(recipient_email)

                if recipients:
                    prompt_subject = f"SmartTravels Parcel Confirmation Request"
                    prompt_body = (
                        f"Dear customer,\n\n"
                        f"A parcel confirmation request has been initiated for sender {sender_name} and receiver {receiver_name}.\n"
                        f"Route: {pickup_location} → {destination}\n"
                        f"Pickup office: {pickup_office}\n"
                        f"Estimated item value: KES {declared_value:.2f}\n"
                        f"Please allow the technical staff to proceed with payment collection.\n\n"
                        f"Thank you,\nSmartTravels Logistics Team"
                    )
                    try:
                        send_mail(prompt_subject, prompt_body, getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@smarttravels.local'), recipients, fail_silently=False)
                        request.session['tech_parcels_prompt_sent'] = True
                        prompt_sent = True
                        messages.success(request, 'Confirmation prompt sent to sender and receiver. Proceed with payment collection.')
                    except Exception as exc:
                        messages.error(request, f'Failed to send confirmation prompt: {exc}')

            if not payment_phone or amount <= 0:
                messages.error(request, 'Specify a payment phone number and amount before sending STK push.')
                return render(request, 'technical_staff/tech_parcels.html', {
                    **default_context,
                    'prompt_sent': prompt_sent,
                    'stk_sent': stk_sent,
                    'form_data': form_data,
                    'active_step': 3,
                })

            try:
                parcel_ref = f"PARCEL-{sender_name.replace(' ', '-')[:10]}-{timezone.now().timestamp()}"
                pay = Payment.objects.create(
                    booking_reference=parcel_ref,
                    booking_type='parcel',
                    passenger=request.user,
                    amount=amount,
                    method='mpesa',
                    phone_number=payment_phone,
                )
                svc = MPesaService()
                res = svc.stk_push(payment_phone, amount, parcel_ref)
                if isinstance(res, dict) and str(res.get('ResponseCode')) == '0':
                    pay.merchant_ref = res.get('CheckoutRequestID', '')
                    pay.save(update_fields=['merchant_ref'])
                    request.session['tech_parcels_stk_sent'] = True
                    request.session['tech_parcels_stk_phone'] = payment_phone
                    stk_sent = True
                    stk_phone = payment_phone

                    # Create parcel and generate waybill immediately after prompting the user.
                    passenger_user = None
                    if sender_email:
                        passenger_user = User.objects.filter(email__iexact=sender_email, role='passenger').first()
                    if not passenger_user and sender_phone:
                        passenger_user = User.objects.filter(phone_number__iexact=sender_phone, role='passenger').first()

                    sender_for_parcel = passenger_user if passenger_user else request.user
                    if passenger_user:
                        sender_name = sender_name or passenger_user.get_full_name() or passenger_user.email
                        sender_email = sender_email or passenger_user.email
                        sender_phone = sender_phone or passenger_user.phone_number

                    parcel = Parcel.objects.create(
                        sender=sender_for_parcel,
                        sender_name=sender_name,
                        sender_phone=sender_phone,
                        sender_email=sender_email,
                        recipient_name=receiver_name,
                        recipient_phone=receiver_phone,
                        recipient_email=recipient_email,
                        origin=pickup_location,
                        destination=destination,
                        category=parcel_type,
                        description=description,
                        item_image=item_image,
                        weight_kg=weight,
                        declared_value=declared_value,
                        shipping_cost=amount,
                        is_fragile=False,
                        is_paid=False,
                        status='booked',
                        notes=f"Pickup office: {pickup_office}",
                    )
                    ParcelLog.objects.create(parcel=parcel, status='booked', note='Registered by technical staff', updated_by=request.user)

                    try:
                        qr_data = f"PARCEL|{parcel.parcel_id}|{pickup_location}|{destination}|{sender_email}|{recipient_email}"
                        qr_image = qrcode.make(qr_data)
                        buffer = io.BytesIO()
                        qr_image.save(buffer, format='PNG')
                        buffer.seek(0)
                        parcel_qr = {'url': 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()}
                        tracking_id = parcel.parcel_id
                    except Exception:
                        parcel_qr = None
                        tracking_id = parcel.parcel_id

                    messages.success(request, f'STK push sent to {payment_phone}. Waybill generated and ready for print.')
                    return render(request, 'technical_staff/tech_parcels.html', {
                        **default_context,
                        'prompt_sent': prompt_sent,
                        'stk_sent': stk_sent,
                        'stk_phone': stk_phone,
                        'form_data': form_data,
                        'parcel_qr': parcel_qr,
                        'tracking_id': tracking_id,
                        'active_step': 4,
                    })
                else:
                    pay.status = 'failed'
                    pay.notes = f"STK failed or unexpected response: {res}"
                    pay.save(update_fields=['status','notes'])
                    messages.error(request, f'STK push failed. Response: {res}')
            except Exception as exc:
                if 'pay' in locals():
                    pay.status = 'failed'
                    pay.notes = f"STK error: {exc}"
                    pay.save(update_fields=['status','notes'])
                messages.error(request, f'Failed to send STK push: {exc}')

            return render(request, 'technical_staff/tech_parcels.html', {
                **default_context,
                'prompt_sent': prompt_sent,
                'stk_sent': stk_sent,
                'stk_phone': stk_phone,
                'form_data': form_data,
                'active_step': 3,
            })

        if prompt_action == 'process_waybill':
            if not request.session.get('tech_parcels_stk_sent'):
                messages.error(request, 'Send and confirm the STK push before processing the waybill.')
                return redirect('tech_parcels')

            if sender_name and sender_phone and receiver_name and receiver_phone and pickup_location and pickup_office and destination:
                passenger_user = None
                if sender_email:
                    passenger_user = User.objects.filter(email__iexact=sender_email, role='passenger').first()
                if not passenger_user and sender_phone:
                    passenger_user = User.objects.filter(phone_number__iexact=sender_phone, role='passenger').first()

                sender_for_parcel = passenger_user if passenger_user else request.user
                if passenger_user:
                    sender_name = sender_name or passenger_user.get_full_name() or passenger_user.email
                    sender_email = sender_email or passenger_user.email
                    sender_phone = sender_phone or passenger_user.phone_number

                parcel = Parcel.objects.create(
                    sender=sender_for_parcel,
                    sender_name=sender_name,
                    sender_phone=sender_phone,
                    sender_email=sender_email,
                    recipient_name=receiver_name,
                    recipient_phone=receiver_phone,
                    recipient_email=recipient_email,
                    origin=pickup_location,
                    destination=destination,
                    category=parcel_type,
                    description=description,
                    item_image=item_image,
                    weight_kg=weight,
                    declared_value=declared_value,
                    shipping_cost=amount,
                    is_fragile=False,
                    is_paid=(payment_status == 'Paid'),
                    status='booked',
                    notes=f"Pickup office: {pickup_office}",
                )
                ParcelLog.objects.create(parcel=parcel, status='booked', note='Registered by technical staff', updated_by=request.user)

                transport_choice = request.POST.get('transport_choice')
                vehicle_assignment = request.POST.get('fleet_assignment', '')
                if vehicle_assignment and ':' in vehicle_assignment:
                    vehicle_type, vehicle_id = vehicle_assignment.split(':', 1)
                    if vehicle_type == 'bus' and vehicle_id:
                        try:
                            from apps.buses.models import Bus
                            b = Bus.objects.filter(id=vehicle_id, company=company).first()
                            if b:
                                parcel.assigned_vehicle_type = 'bus'
                                parcel.assigned_vehicle_id = b.id
                                parcel.assigned_vehicle_name = str(b)
                        except Exception:
                            pass
                    elif vehicle_type == 'train' and vehicle_id:
                        try:
                            from apps.trains.models import Train
                            t = Train.objects.filter(id=vehicle_id, company=company).first()
                            if t:
                                parcel.assigned_vehicle_type = 'train'
                                parcel.assigned_vehicle_id = t.id
                                parcel.assigned_vehicle_name = str(t)
                        except Exception:
                            pass
                    elif vehicle_type == 'flight' and vehicle_id:
                        try:
                            from apps.flights.models import Flight
                            f = Flight.objects.filter(id=vehicle_id, company=company).first()
                            if f:
                                parcel.assigned_vehicle_type = 'flight'
                                parcel.assigned_vehicle_id = f.id
                                parcel.assigned_vehicle_name = str(f)
                        except Exception:
                            pass
                elif request.POST.get('truck'):
                    parcel.assigned_vehicle_type = 'truck'
                    parcel.assigned_vehicle_name = f"Truck {request.POST.get('truck')}"

                parcel.save()
                request.session.pop('tech_parcels_prompt_sent', None)
                request.session.pop('tech_parcels_stk_sent', None)
                request.session.pop('tech_parcels_stk_phone', None)

                try:
                    recipients = []
                    if sender_email:
                        recipients.append(sender_email)
                    if recipient_email and recipient_email != sender_email:
                        recipients.append(recipient_email)
                    if recipients:
                        receipt_subject = f"SmartTravels Parcel Registered: {parcel.parcel_id}"
                        receipt_body = (
                            f"Hello,\n\nYour parcel has been registered and the waybill has been generated.\n"
                            f"Tracking ID: {parcel.parcel_id}\n"
                            f"Route: {pickup_location} → {destination}\n"
                            f"Declared item value: KES {declared_value:.2f}\n"
                            f"Shipping fee: KES {amount:.2f}\n\n"
                            f"Thank you for using SmartTravels."
                        )
                        send_mail(receipt_subject, receipt_body, getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@smarttravels.local'), recipients, fail_silently=True)
                except Exception:
                    pass

                try:
                    qr_data = f"PARCEL|{parcel.parcel_id}|{pickup_location}|{destination}|{sender_email}|{recipient_email}"
                    qr_image = qrcode.make(qr_data)
                    buffer = io.BytesIO()
                    qr_image.save(buffer, format='PNG')
                    buffer.seek(0)
                    parcel_qr = {'url': 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()}
                    tracking_id = parcel.parcel_id
                except Exception:
                    parcel_qr = None
                    tracking_id = parcel.parcel_id

                messages.success(request, 'Waybill processed and QR code generated. You can print the label now.')
                return render(request, 'technical_staff/tech_parcels.html', {
                    **default_context,
                    'parcel_qr': parcel_qr,
                    'tracking_id': tracking_id,
                    'active_step': 4,
                    'sender_name': sender_name,
                    'receiver_name': receiver_name,
                    'pickup_location': pickup_location,
                    'destination': destination,
                    'parcel_type': parcel_type,
                    'weight': weight,
                    'amount': amount,
                })

    return render(request, 'technical_staff/tech_parcels.html', {
        'company_name': company_name,
        'routes': routes,
        'stations': stations,
        'available_vehicles': available_vehicles,
        'buses': buses,
        'trains': trains,
        'flights': flights,
        'parcel_qr': parcel_qr,
        'tracking_id': tracking_id,
        'prompt_sent': prompt_sent,
        'stk_sent': stk_sent,
        'stk_phone': stk_phone,
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

    staff_parcels = Parcel.objects.filter(sender=request.user).order_by('-updated_at')
    staff_parcels_in_transit = staff_parcels.filter(status='in_transit').count()
    staff_pending_pickups = staff_parcels.filter(status__in=['booked', 'dropped_off']).count()
    staff_picked_up = staff_parcels.filter(status__in=['arrived', 'collected']).count()

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
        'staff_parcels': staff_parcels,
        'staff_parcels_in_transit': staff_parcels_in_transit,
        'staff_pending_pickups': staff_pending_pickups,
        'staff_picked_up': staff_picked_up,
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
